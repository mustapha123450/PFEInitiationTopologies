#!/usr/bin/env python3
"""
SCRIPT DE MONITORING IOT - VERSION FINALE
- Mesure toutes les 90 secondes
- Migration automatique si une condition critique est atteinte
- Toi tu bombardes avec des requêtes depuis un autre terminal
"""

import requests
import subprocess
import json
import time
import sys
import os
import urllib3
from datetime import datetime
from pathlib import Path

# Importer les fonctions du script de routage
import sys
sys.path.append('.')
try:
    from redirect_gf1_to_inter2 import architecture_modifiee, architecture_nominale
    ROUTING_AVAILABLE = True
except ImportError:
    print("⚠️  Script de routage non trouvé - mode simulation uniquement")
    ROUTING_AVAILABLE = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================
# CONFIGURATION
# =============================================
NAMESPACE = "iot-topology"
MONITORING_INTERVAL = 90  # 90 secondes entre chaque mesure
LOG_DIR = "./monitoring_logs"

# SEUILS POUR DÉCLENCHER LA TOPOLOGIE 2
THRESHOLDS = {
    # Seuils pour GF1 (déclencheur de migration)
    'gf1_qps_critical': 10,        # 10 req/s
    'gf1_qps_warning': 7,           # 7 req/s
    'gf1_latency_critical': 50,     # 50 ms
    'gf1_latency_warning': 30,      # 30 ms
    'gf1_cpu_critical': 30,         # 30 millicores
    'gf1_cpu_warning': 20,          # 20 millicores
       
    # Seuils pour retour à la normale (plus bas)
    'gf1_qps_normal': 5,            # En dessous de 5 req/s
    'gf1_latency_normal': 25,       # En dessous de 25 ms
    'gf1_cpu_normal': 1,
    
    # Seuils pour alertes (non déclencheurs de migration)
    'inter1_latency_warning': 40,   # 40 ms
    'inter1_qps_warning': 15,       # 15 req/s
}

# État actuel de la topologie
current_topology = "nominale"  # "nominale" ou "modifiee"
migration_in_progress = False  # Évite les migrations multiples
last_migration_time = 0
MIGRATION_COOLDOWN = 300  # 5 minutes de cooldown après migration

# =============================================
# FONCTIONS DE BASE
# =============================================
# Ajoute ces seuils pour le retour à la normale
THRESHOLDS.update({
    # Seuils pour retour à la topologie nominale (plus bas que les seuils critiques)
    'gf1_qps_normal': 5,         # En dessous de 5 req/s
    'gf1_latency_normal': 25,    # En dessous de 25 ms
    'gf1_cpu_normal': 15,        # En dessous de 15 millicores
})

def check_return_to_normal(gateway_metrics, cpu_metrics):
    """Vérifie si on peut revenir à la topologie nominale"""
    global current_topology, migration_in_progress, last_migration_time
    
    if current_topology != "modifiee" or migration_in_progress:
        return False, []
    
    # Récupérer les métriques de GF1
    gf1_metrics = gateway_metrics['gateways_finales'].get('iot-gateway-final-1', {})
    
    # Récupérer le CPU de GF1
    gf1_cpu = 0
    for pod in cpu_metrics:
        if 'final-1' in pod['name']:
            for container in pod['containers']:
                if container['name'] == 'gateway':
                    gf1_cpu = container['cpu_millicores']
    
    current_qps = gf1_metrics.get('qps', 0)
    current_latency = gf1_metrics.get('latency_p95', 0)
    
    alerts = []
    should_return = False
    
    # Vérifier si toutes les métriques sont redevenues normales
    qps_normal = current_qps < THRESHOLDS['gf1_qps_normal']
    latency_normal = current_latency < THRESHOLDS['gf1_latency_normal']
    cpu_normal = gf1_cpu < THRESHOLDS['gf1_cpu_normal']
    
    if qps_normal and latency_normal and cpu_normal:
        alerts.append(f"🟢 TOUTES LES MÉTRIQUES SONT REDEVENUES NORMALES")
        alerts.append(f"   QPS: {current_qps:.1f} < {THRESHOLDS['gf1_qps_normal']}")
        alerts.append(f"   Latence: {current_latency:.1f} < {THRESHOLDS['gf1_latency_normal']}")
        alerts.append(f"   CPU: {gf1_cpu:.1f} < {THRESHOLDS['gf1_cpu_normal']}")
        should_return = True
    
    return should_return, alerts
def get_api_info():
    """Récupère l'URL de l'API et un token"""
    try:
        api_server = subprocess.check_output(
            "kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'", 
            shell=True, text=True
        ).strip().strip("'")
        
        token = subprocess.check_output(
            "kubectl create token default -n iot-topology --duration=3600s", 
            shell=True, text=True
        ).strip()
        
        return api_server, token
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)

def setup_prometheus_port_forward():
    """Configure le port-forward pour Prometheus"""
    try:
        result = subprocess.run(
            "pgrep -f 'kubectl port-forward.*prometheus'",
            shell=True, capture_output=True
        )
        
        if result.returncode != 0:
            print("🔄 Lancement du port-forward Prometheus...")
            subprocess.Popen(
                "kubectl port-forward -n istio-system svc/prometheus 9090:9090 > /dev/null 2>&1 &",
                shell=True
            )
            time.sleep(3)
            return True
        return True
    except:
        return False

# =============================================
# FONCTIONS DE COLLECTE - CPU/RAM POUR TOUS
# =============================================

def collect_all_pods_metrics(api_server, token):
    """Collecte les métriques CPU/RAM de TOUS les pods"""
    
    url = f"{api_server}/apis/metrics.k8s.io/v1beta1/namespaces/{NAMESPACE}/pods"
    headers = {'Authorization': f'Bearer {token}'}
    
    all_metrics = []
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            for pod in data.get('items', []):
                pod_name = pod['metadata']['name']
                
                pod_data = {
                    'name': pod_name,
                    'type': classify_pod(pod_name),
                    'containers': []
                }
                
                for container in pod.get('containers', []):
                    cpu = container['usage']['cpu']
                    memory = container['usage']['memory']
                    
                    cpu_value = parse_cpu(cpu)
                    memory_value = parse_memory(memory)
                    
                    pod_data['containers'].append({
                        'name': container['name'],
                        'cpu_millicores': cpu_value,
                        'cpu_raw': cpu,
                        'memory_mb': memory_value,
                        'memory_raw': memory
                    })
                
                all_metrics.append(pod_data)
    except Exception as e:
        print(f"⚠️  Erreur collecte metrics: {e}")
    
    return all_metrics

def classify_pod(pod_name):
    """Classifie un pod par son type"""
    if 'device-gf' in pod_name:
        return 'device'
    elif 'gateway-final' in pod_name:
        return 'gateway_finale'
    elif 'gateway-inter' in pod_name:
        return 'gateway_inter'
    elif 'server' in pod_name:
        return 'server'
    elif 'application' in pod_name:
        return 'application'
    else:
        return 'autre'

def parse_cpu(cpu_str):
    """Convertit la chaîne CPU en millicores"""
    if cpu_str.endswith('n'):
        return int(cpu_str[:-1]) / 1_000_000
    elif cpu_str.endswith('u'):
        return int(cpu_str[:-1]) / 1000
    elif cpu_str.endswith('m'):
        return int(cpu_str[:-1])
    else:
        return int(cpu_str) * 1000

def parse_memory(mem_str):
    """Convertit la chaîne mémoire en MB"""
    if mem_str.endswith('Ki'):
        return int(mem_str[:-2]) / 1024
    elif mem_str.endswith('Mi'):
        return int(mem_str[:-2])
    elif mem_str.endswith('Gi'):
        return int(mem_str[:-2]) * 1024
    else:
        return int(mem_str) / (1024 * 1024)

# =============================================
# FONCTIONS DE COLLECTE - LATENCE ET BANDE PASSANTE
# =============================================

def query_prometheus(query):
    """Exécute une requête Prometheus"""
    url = "http://localhost:9090/api/v1/query"
    params = {'query': query}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            return response.json().get('data', {}).get('result', [])
        else:
            return []
    except:
        return []

def collect_gateway_metrics():
    """Collecte les métriques spécifiques aux gateways"""
    
    setup_prometheus_port_forward()
    time.sleep(1)
    
    metrics = {
        'gateways_finales': {},
        'gateways_inter': {}
    }
    
    # Liste des gateways à surveiller
    gateways = {
        'gateways_finales': ['iot-gateway-final-1', 'iot-gateway-final-2', 'iot-gateway-final-3'],
        'gateways_inter': ['iot-gateway-inter-1', 'iot-gateway-inter-2']
    }
    
    for category, gw_list in gateways.items():
        for gw in gw_list:
            metrics[category][gw] = {
                'qps': 0,
                'latency_p95': 0,
                'bandwidth_in': 0,
                'bandwidth_out': 0,
                'error_rate': 0
            }
            
            # QPS total reçu par cette gateway
            qps_query = f'sum(rate(istio_requests_total{{namespace="{NAMESPACE}", destination_workload="{gw}"}}[1m]))'
            qps_result = query_prometheus(qps_query)
            if qps_result:
                metrics[category][gw]['qps'] = float(qps_result[0]['value'][1])
            
            # Latence p95
            latency_query = f'histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket{{namespace="{NAMESPACE}", destination_workload="{gw}"}}[1m])) by (le))'
            latency_result = query_prometheus(latency_query)
            if latency_result:
                metrics[category][gw]['latency_p95'] = float(latency_result[0]['value'][1])
            
            # Bande passante entrante (bytes reçus)
            bw_in_query = f'sum(rate(istio_request_bytes_sum{{namespace="{NAMESPACE}", destination_workload="{gw}"}}[1m]))'
            bw_in_result = query_prometheus(bw_in_query)
            if bw_in_result:
                metrics[category][gw]['bandwidth_in'] = float(bw_in_result[0]['value'][1])
            
            # Bande passante sortante (bytes envoyés)
            bw_out_query = f'sum(rate(istio_response_bytes_sum{{namespace="{NAMESPACE}", source_workload="{gw}"}}[1m]))'
            bw_out_result = query_prometheus(bw_out_query)
            if bw_out_result:
                metrics[category][gw]['bandwidth_out'] = float(bw_out_result[0]['value'][1])
            
            # Taux d'erreur
            error_query = f'sum(rate(istio_requests_total{{namespace="{NAMESPACE}", destination_workload="{gw}", response_code=~"5.."}}[1m])) / sum(rate(istio_requests_total{{namespace="{NAMESPACE}", destination_workload="{gw}"}}[1m])) * 100'
            error_result = query_prometheus(error_query)
            if error_result and len(error_result) > 0:
                metrics[category][gw]['error_rate'] = float(error_result[0]['value'][1])
    
    return metrics

# =============================================
# FONCTION DE DÉTECTION ET TRIGGER
# =============================================

def check_thresholds(gateway_metrics, cpu_metrics):
    """Vérifie les seuils et déclenche la migration ou le retour si nécessaire"""
    global current_topology, migration_in_progress, last_migration_time
    
    alerts = {
        'critical': [],
        'warning': [],
        'info': []
    }
    should_switch = False
    should_return = False
    
    # Récupérer les métriques de GF1
    gf1_metrics = gateway_metrics['gateways_finales'].get('iot-gateway-final-1', {})
    
    # Récupérer le CPU de GF1
    gf1_cpu = 0
    for pod in cpu_metrics:
        if 'final-1' in pod['name']:
            for container in pod['containers']:
                if container['name'] == 'gateway':
                    gf1_cpu = container['cpu_millicores']
    
    # --- SI ON EST EN TOPOLOGIE MODIFIÉE, VÉRIFIER SI ON PEUT REVENIR ---
    if current_topology == "modifiee" and not migration_in_progress:
        current_qps = gf1_metrics.get('qps', 0)
        current_latency = gf1_metrics.get('latency_p95', 0)
        
        # Vérifier si TOUTES les métriques sont redevenues normales
        if (current_qps < THRESHOLDS['gf1_qps_normal'] and 
            current_latency < THRESHOLDS['gf1_latency_normal'] and 
            gf1_cpu < THRESHOLDS['gf1_cpu_normal']):
            
            alerts['info'].append(f"🟢 MÉTRIQUES NORMALES - RETOUR TOPOLOGIE 1")
            alerts['info'].append(f"   QPS: {current_qps:.1f} (normal < {THRESHOLDS['gf1_qps_normal']})")
            alerts['info'].append(f"   Latence: {current_latency:.1f} (normal < {THRESHOLDS['gf1_latency_normal']})")
            alerts['info'].append(f"   CPU: {gf1_cpu:.1f} (normal < {THRESHOLDS['gf1_cpu_normal']})")
            should_return = True
    
    # --- SINON, VÉRIFIER LES SEUILS CRITIQUES POUR MIGRER ---
    else:
        current_qps = gf1_metrics.get('qps', 0)
        if current_qps > THRESHOLDS['gf1_qps_critical']:
            alerts['critical'].append(f"🔴 GF1 QPS CRITIQUE: {current_qps:.1f} req/s")
            should_switch = True
        
        current_latency = gf1_metrics.get('latency_p95', 0)
        if current_latency > THRESHOLDS['gf1_latency_critical']:
            alerts['critical'].append(f"🔴 GF1 LATENCE CRITIQUE: {current_latency:.1f} ms")
            should_switch = True
        
        if gf1_cpu > THRESHOLDS['gf1_cpu_critical']:
            alerts['critical'].append(f"🔴 GF1 CPU CRITIQUE: {gf1_cpu:.1f}m")
            should_switch = True
        
        # --- VÉRIFICATION DES SEUILS WARNING ---
        if current_qps > THRESHOLDS['gf1_qps_warning'] and current_qps <= THRESHOLDS['gf1_qps_critical']:
            alerts['warning'].append(f"🟡 GF1 QPS ÉLEVÉ: {current_qps:.1f} req/s")
        
        if current_latency > THRESHOLDS['gf1_latency_warning'] and current_latency <= THRESHOLDS['gf1_latency_critical']:
            alerts['warning'].append(f"🟡 GF1 LATENCE ÉLEVÉE: {current_latency:.1f} ms")
        
        if gf1_cpu > THRESHOLDS['gf1_cpu_warning'] and gf1_cpu <= THRESHOLDS['gf1_cpu_critical']:
            alerts['warning'].append(f"🟡 GF1 CPU ÉLEVÉ: {gf1_cpu:.1f}m")
        
        # Alertes sur inter-1
        inter1_metrics = gateway_metrics['gateways_inter'].get('iot-gateway-inter-1', {})
        if inter1_metrics.get('latency_p95', 0) > THRESHOLDS['inter1_latency_warning']:
            alerts['warning'].append(f"🟡 inter-1 LATENCE ÉLEVÉE: {inter1_metrics['latency_p95']:.1f} ms")
        
        if inter1_metrics.get('qps', 0) > THRESHOLDS['inter1_qps_warning']:
            alerts['warning'].append(f"🟡 inter-1 TRAFIC ÉLEVÉ: {inter1_metrics['qps']:.1f} req/s")
    
    # --- DÉCLENCHEMENT DE LA MIGRATION OU DU RETOUR ---
    current_time = time.time()
    
    if should_switch and current_topology == "nominale" and not migration_in_progress:
        if current_time - last_migration_time > MIGRATION_COOLDOWN:
            print("\n" + "="*80)
            print("🚨 DÉCLENCHEMENT DE LA MIGRATION VERS TOPOLOGIE 2")
            print("="*80)
            for alert in alerts['critical']:
                print(f"   {alert}")
            print("\n🔀 Migration en cours...")
            
            migration_in_progress = True
            
            try:
                if ROUTING_AVAILABLE:
                    architecture_modifiee()
                    current_topology = "modifiee"
                    last_migration_time = time.time()
                    print("✅ Topologie 2 activée avec succès !")
                else:
                    print("⚠️  Mode simulation - migration simulée")
                    current_topology = "modifiee"
                    last_migration_time = time.time()
            except Exception as e:
                print(f"❌ Erreur lors de la migration: {e}")
            finally:
                migration_in_progress = False
        else:
            cooldown_remaining = MIGRATION_COOLDOWN - (current_time - last_migration_time)
            print(f"\n⏳ Migration en cooldown ({cooldown_remaining:.0f}s restantes)")
    
    elif should_return and current_topology == "modifiee" and not migration_in_progress:
        print("\n" + "="*80)
        print("🟢 RETOUR À LA TOPOLOGIE NOMINALE")
        print("="*80)
        for alert in alerts['info']:
            print(f"   {alert}")
        print("\n🔄 Retour en cours...")
        
        migration_in_progress = True
        
        try:
            if ROUTING_AVAILABLE:
                architecture_nominale()
                current_topology = "nominale"
                last_migration_time = time.time()
                print("✅ Topologie nominale restaurée avec succès !")
            else:
                print("⚠️  Mode simulation - retour simulé")
                current_topology = "nominale"
                last_migration_time = time.time()
        except Exception as e:
            print(f"❌ Erreur lors du retour: {e}")
        finally:
            migration_in_progress = False
    
    return alerts, (should_switch or should_return)

# =============================================
# FONCTIONS DE STOCKAGE
# =============================================

def save_metrics(all_metrics):
    """Sauvegarde les métriques dans un fichier JSON"""
    
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{LOG_DIR}/monitoring_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)
    
    return filename

# =============================================
# FONCTIONS D'AFFICHAGE
# =============================================

def display_cpu_ram(cpu_metrics):
    """Affiche les métriques CPU/RAM pour tous les pods"""
    
    print("\n💻 [CPU/RAM - TOUS LES PODS]")
    print("-" * 80)
    
    categories = {
        'gateway_inter': 'GATEWAYS INTER',
        'gateway_finale': 'GATEWAYS FINALES',
        'server': 'SERVER',
        'application': 'APPLICATIONS',
        'device': 'DEVICES',
        'autre': 'AUTRES'
    }
    
    for category_name, display_name in categories.items():
        print(f"\n   📌 {display_name}:")
        found = False
        for pod in cpu_metrics:
            if pod['type'] == category_name:
                found = True
                print(f"      📦 {pod['name'][:40]}:")
                for container in pod['containers']:
                    print(f"         • {container['name']}: CPU {container['cpu_millicores']:.1f}m | RAM {container['memory_mb']:.1f}MB")
        if not found:
            print(f"      ⚠️  Aucun pod trouvé")

def display_gateway_metrics(gateway_metrics):
    """Affiche les métriques des gateways (latence, bande passante)"""
    
    print("\n📊 [MÉTRIQUES GATEWAYS - LATENCE & BANDE PASSANTE]")
    print("-" * 80)
    
    print("\n   🚦 GATEWAYS FINALES:")
    for gw_name, metrics in gateway_metrics['gateways_finales'].items():
        print(f"\n      📍 {gw_name}:")
        print(f"         • QPS reçu: {metrics['qps']:.2f} req/s")
        print(f"         • Latence p95: {metrics['latency_p95']:.1f} ms")
        print(f"         • Bande passante IN: {metrics['bandwidth_in']/1024:.2f} KB/s")
        print(f"         • Bande passante OUT: {metrics['bandwidth_out']/1024:.2f} KB/s")
        print(f"         • Taux d'erreur: {metrics['error_rate']:.2f}%")
    
    print("\n   🚦 GATEWAYS INTERMÉDIAIRES:")
    for gw_name, metrics in gateway_metrics['gateways_inter'].items():
        print(f"\n      📍 {gw_name}:")
        print(f"         • QPS reçu: {metrics['qps']:.2f} req/s")
        print(f"         • Latence p95: {metrics['latency_p95']:.1f} ms")
        print(f"         • Bande passante IN: {metrics['bandwidth_in']/1024:.2f} KB/s")
        print(f"         • Bande passante OUT: {metrics['bandwidth_out']/1024:.2f} KB/s")
        print(f"         • Taux d'erreur: {metrics['error_rate']:.2f}%")

def display_topology_status():
    """Affiche le statut de la topologie actuelle"""
    
    status_color = "🟢" if current_topology == "nominale" else "🔵"
    migration_status = " (migration en cours...)" if migration_in_progress else ""
    print(f"\n📍 TOPOLOGIE ACTUELLE: {status_color} {current_topology.upper()}{migration_status}")

# =============================================
# FONCTION PRINCIPALE DE MONITORING
# =============================================

def monitoring_loop():
    """Boucle principale de monitoring - Mesure toutes les 90 secondes"""
    global current_topology
    
    print("\n" + "="*100)
    print("🚀 MONITORING IOT - MESURE TOUTES LES 90 SECONDES")
    print("="*100)
    print(f"""
📊 SEUILS DE MIGRATION (GF1):
   • QPS critique: {THRESHOLDS['gf1_qps_critical']} req/s
   • Latence critique: {THRESHOLDS['gf1_latency_critical']} ms
   • CPU critique: {THRESHOLDS['gf1_cpu_critical']}m

⏱️  INTERVALLE DE MESURE: {MONITORING_INTERVAL} secondes
📝 COOLDOWN APRÈS MIGRATION: {MIGRATION_COOLDOWN//60} minutes

📌 INSTRUCTIONS:
   • Laisse ce script tourner dans Terminal 1
   • Dans Terminal 2, bombarde GF1 avec des requêtes
   • La migration se fera automatiquement au prochain cycle
    """)
    
    api_server, token = get_api_info()
    cycle_count = 0
    
    try:
        while True:
            cycle_start = time.time()
            cycle_count += 1
            
            print(f"\n{'='*100}")
            print(f"🔄 CYCLE DE MESURE #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*100}")
            
            print("\n⏳ Collecte des métriques en cours...")
            
            # Collecter TOUTES les données
            cpu_metrics = collect_all_pods_metrics(api_server, token)
            gateway_metrics = collect_gateway_metrics()
            
            # Afficher le statut de la topologie
            display_topology_status()
            
            # Afficher CPU/RAM pour tous
            display_cpu_ram(cpu_metrics)
            
            # Afficher les métriques des gateways
            display_gateway_metrics(gateway_metrics)
            
            # Vérifier les seuils et déclencher migration si nécessaire
            alerts, switched = check_thresholds(gateway_metrics, cpu_metrics)
            
            # Afficher les alertes
            if alerts['critical'] or alerts['warning']:
                print("\n🚨 ALERTES:")
                for alert in alerts['critical']:
                    print(f"   {alert}")
                for alert in alerts['warning']:
                    print(f"   {alert}")
            
            # Sauvegarder les données
            all_metrics = {
                'timestamp': datetime.now().isoformat(),
                'cycle': cycle_count,
                'topology': current_topology,
                'migration_in_progress': migration_in_progress,
                'cpu_metrics': cpu_metrics,
                'gateway_metrics': gateway_metrics,
                'alerts': alerts,
                'migration_triggered': switched
            }
            filename = save_metrics(all_metrics)
            print(f"\n💾 Données sauvegardées: {filename}")
            
            # Calculer le temps d'attente jusqu'au prochain cycle
            cycle_duration = time.time() - cycle_start
            sleep_time = max(0, MONITORING_INTERVAL - cycle_duration)
            
            print(f"\n⏳ Prochaine mesure dans {sleep_time:.0f} secondes... (Ctrl+C pour arrêter)")
            print(f"   Pendant ce temps, bombarde GF1 dans un autre terminal !")
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring arrêté")
        print(f"📊 {cycle_count} cycles complétés")
        print(f"📍 Dernière topologie: {current_topology}")

# =============================================
# FONCTION POUR RETOURNER À LA TOPOLOGIE NOMINALE
# =============================================

def return_to_nominal():
    """Retourne à la topologie nominale"""
    global current_topology, last_migration_time
    
    print("\n🔄 Retour à la topologie nominale...")
    
    try:
        if ROUTING_AVAILABLE:
            architecture_nominale()
            current_topology = "nominale"
            last_migration_time = time.time()
            print("✅ Topologie nominale restaurée avec succès !")
        else:
            print("⚠️  Mode simulation - retour simulé")
            current_topology = "nominale"
            last_migration_time = time.time()
    except Exception as e:
        print(f"❌ Erreur lors du retour: {e}")

# =============================================
# MENU PRINCIPAL
# =============================================

if __name__ == "__main__":
    print("\n" + "="*100)
    print("🚀 MONITORING IOT - VERSION FINALE")
    print("="*100)
    print("""
    📌 COMMENT UTILISER:
    
    ▸ TERMINAL 1 (ce script):
      • Lance l'option 1 pour démarrer le monitoring
      • Le script mesure toutes les 90 secondes
      • Il migre automatiquement vers topologie 2 si seuils dépassés
    
    ▸ TERMINAL 2 (toi):
      • Bombarde GF1 avec des requêtes
      • Utilise la commande: 
        for i in {1..1000}; do 
          kubectl exec -n iot-topology deployment/device-gf1-1 -- wget -qO- http://iot-gateway-final-1:8281/health > /dev/null 2>&1
          sleep 0.1
        done
    
    ▸ SEUILS DE MIGRATION:
      • QPS > 10 req/s
      • Latence > 50 ms
      • CPU > 30 millicores
    
    ▸ COOLDOWN: 5 minutes après une migration
    """)
    
    while True:
        print("\n" + "="*60)
        print("MENU PRINCIPAL")
        print("="*60)
        print("""
    1. 🚀 Lancer le monitoring (mesures toutes les 90s)
    2. 🔄 Retour à la topologie nominale
    3. 📊 Voir l'état actuel
    0. ❌ Quitter
        """)
        
        choix = input("Votre choix (0-3): ")
        
        if choix == "1":
            monitoring_loop()
        elif choix == "2":
            return_to_nominal()
        elif choix == "3":
            print(f"\n📍 Topologie actuelle: {current_topology}")
            print(f"⏱️  Dernière migration: {datetime.fromtimestamp(last_migration_time).strftime('%H:%M:%S') if last_migration_time > 0 else 'Jamais'}")
        elif choix == "0":
            print("👋 Au revoir!")
            break
        else:
            print("❌ Choix invalide")
