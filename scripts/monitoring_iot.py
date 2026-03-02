#!/usr/bin/env python3
"""
SCRIPT DE MONITORING IOT - MIGRATION INSTANTANÉE CORRIGÉ
- Migration immédiate dès que conditions remplies ET cooldown terminé
- Cooldown de 3 minutes après chaque migration
- PAS de timer supplémentaire pour le retour !
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
import threading

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
MONITORING_INTERVAL = 1  # 1 seconde
LOG_DIR = "./monitoring_logs"

# SEUILS
THRESHOLDS = {
    'gf1_qps_critical': 10,     # Seuil pour aller vers topologie 2
    'gf1_qps_normal': 5,         # Seuil pour revenir vers topologie 1
}

# État
current_topology = "nominale"      # "nominale" ou "modifiee"
migration_in_progress = False
migration_start_time = 0
last_change_time = 0                # Timestamp du dernier changement
COOLDOWN_DURATION = 180              # 180 secondes = 3 minutes de cooldown

# =============================================
# FONCTIONS DE BASE
# =============================================

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
            time.sleep(2)
            return True
        return True
    except:
        return False

def query_prometheus(query):
    """Exécute une requête Prometheus"""
    url = "http://localhost:9090/api/v1/query"
    params = {'query': query}
    
    try:
        response = requests.get(url, params=params, timeout=3)
        if response.status_code == 200:
            return response.json().get('data', {}).get('result', [])
        else:
            return []
    except:
        return []

def get_gf1_qps():
    """Récupère uniquement le QPS de gateway-final-1"""
    
    setup_prometheus_port_forward()
    
    # Fenêtre de 30s pour plus de réactivité
    query = f'sum(rate(istio_requests_total{{namespace="{NAMESPACE}", destination_workload="iot-gateway-final-1"}}[30s]))'
    result = query_prometheus(query)
    
    if result:
        return float(result[0]['value'][1])
    return 0.0

def migrer_vers_topologie2():
    """Migre vers la topologie 2 - INSTANTANÉ"""
    global current_topology, last_change_time, migration_in_progress
    
    print("\n" + "="*90)
    print("🚨 MIGRATION VERS TOPOLOGIE 2")
    print("="*90)
    print(f"   • QPS > {THRESHOLDS['gf1_qps_critical']} req/s détecté")
    print(f"   • Migration INSTANTANÉE en cours...")
    
    try:
        if ROUTING_AVAILABLE:
            architecture_modifiee()
            current_topology = "modifiee"
            last_change_time = time.time()
            print(f"\n✅ Topologie 2 activée avec succès !")
        else:
            print("⚠️  Mode simulation - migration simulée")
            current_topology = "modifiee"
            last_change_time = time.time()
            print(f"\n✅ Topologie 2 activée (simulation)")
        
        print(f"⏳ COOLDOWN DE 3 MINUTES DÉBUTÉ ({COOLDOWN_DURATION} secondes)")
        print(f"   • Prochain changement possible dans 3 minutes")
    except Exception as e:
        print(f"\n❌ Erreur lors de la migration: {e}")
    finally:
        migration_in_progress = False
        print("="*90)

def migrer_vers_topologie1():
    """Migre vers la topologie 1 - INSTANTANÉ"""
    global current_topology, last_change_time, migration_in_progress
    
    print("\n" + "="*90)
    print("🟢 RETOUR VERS TOPOLOGIE 1")
    print("="*90)
    print(f"   • Trafic normal détecté après cooldown")
    print(f"   • Migration INSTANTANÉE en cours...")
    
    try:
        if ROUTING_AVAILABLE:
            architecture_nominale()
            current_topology = "nominale"
            last_change_time = time.time()
            print(f"\n✅ Topologie 1 restaurée avec succès !")
        else:
            print("⚠️  Mode simulation - retour simulé")
            current_topology = "nominale"
            last_change_time = time.time()
            print(f"\n✅ Topologie 1 restaurée (simulation)")
        
        print(f"⏳ COOLDOWN DE 3 MINUTES DÉBUTÉ ({COOLDOWN_DURATION} secondes)")
    except Exception as e:
        print(f"\n❌ Erreur lors du retour: {e}")
    finally:
        migration_in_progress = False
        print("="*90)

def format_time(seconds):
    """Formate les secondes en minutes:secondes"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"

# =============================================
# FONCTION PRINCIPALE CORRIGÉE
# =============================================

def monitoring_loop():
    """Boucle principale de monitoring - Migration instantanée corrigée"""
    global current_topology, migration_in_progress, last_change_time
    
    print("\n" + "="*100)
    print("🚀 MONITORING IOT - MIGRATION INSTANTANÉE CORRIGÉE")
    print("="*100)
    print(f"""
📊 CONFIGURATION:
   • Intervalle de mesure: {MONITORING_INTERVAL} seconde
   • Migration: INSTANTANÉE
   • COOLDOWN après migration: {COOLDOWN_DURATION} secondes (3 minutes)
   
📈 SEUILS:
   • Topologie 1 → Topologie 2: QPS > {THRESHOLDS['gf1_qps_critical']} req/s
   • Topologie 2 → Topologie 1: QPS < {THRESHOLDS['gf1_qps_normal']} req/s

🔄 RÈGLES CORRIGÉES:
   1. Migration immédiate vers topologie 2 si QPS > 10 ET cooldown terminé
   2. Migration immédiate vers topologie 1 si QPS < 5 ET cooldown terminé
   3. PAS de timer supplémentaire de 3 minutes pour le retour !
   4. Après chaque migration, cooldown de 3 minutes
    """)
    
    # Initialisation
    get_api_info()
    setup_prometheus_port_forward()
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            current_time = time.time()
            
            # Récupérer le QPS
            qps = get_gf1_qps()
            
            # Calculer le temps écoulé depuis dernier changement
            time_since_change = current_time - last_change_time if last_change_time > 0 else COOLDOWN_DURATION + 1
            cooldown_remaining = max(0, COOLDOWN_DURATION - time_since_change)
            cooldown_actif = cooldown_remaining > 0
            
            # --- AFFICHAGE PRINCIPAL ---
            status_icon = "🟢" if current_topology == "nominale" else "🔵"
            
            # Construction de la ligne de statut
            status_line = f"\r{status_icon} [{current_topology.upper()}] "
            status_line += f"QPS: {qps:.2f} req/s | "
            
            # Si une migration est en cours
            if migration_in_progress:
                status_line += f"⚡ MIGRATION EN COURS...   "
            
            # Sinon, afficher cooldown
            else:
                if cooldown_actif:
                    temps_format = format_time(cooldown_remaining)
                    status_line += f"⏳ COOLDOWN: {temps_format}"
                else:
                    status_line += f"✓ PRÊT                "
            
            print(status_line, end="", flush=True)
            
            # --- LOGIQUE DE MIGRATION CORRIGÉE ---
            if not migration_in_progress:
                
                # CAS 1: Topologie nominale → migration vers topologie 2
                if current_topology == "nominale":
                    if not cooldown_actif and qps > THRESHOLDS['gf1_qps_critical']:
                        migration_in_progress = True
                        thread = threading.Thread(target=migrer_vers_topologie2)
                        thread.start()
                    
                    elif qps > THRESHOLDS['gf1_qps_critical'] and cooldown_actif and cycle_count % 10 == 0:
                        temps_format = format_time(cooldown_remaining)
                        print(f"\n⏸️  Migration BLOQUÉE - Cooldown encore actif ({temps_format} restantes)")
                
                # CAS 2: Topologie modifiée → migration vers topologie 1
                elif current_topology == "modifiee":
                    
                    # Migration immédiate si cooldown terminé ET trafic normal
                    if not cooldown_actif and qps < THRESHOLDS['gf1_qps_normal']:
                        print(f"\n🟢 Trafic normal détecté après cooldown - Migration immédiate vers topologie 1")
                        migration_in_progress = True
                        thread = threading.Thread(target=migrer_vers_topologie1)
                        thread.start()
                    
                    # Message si trafic normal mais cooldown actif
                    elif qps < THRESHOLDS['gf1_qps_normal'] and cooldown_actif and cycle_count % 10 == 0:
                        temps_format = format_time(cooldown_remaining)
                        print(f"\n⏸️  Retour BLOQUÉ - Cooldown encore actif ({temps_format} restantes)")
            
            # Attendre 1 seconde
            time.sleep(MONITORING_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring arrêté")
        print(f"📊 {cycle_count} mesures effectuées")
        print(f"📍 Dernière topologie: {current_topology}")

# =============================================
# MENU PRINCIPAL
# =============================================

if __name__ == "__main__":
    print("\n" + "="*100)
    print("🚀 MONITORING IOT - MIGRATION INSTANTANÉE CORRIGÉE")
    print("="*100)
    print("""
    📌 FONCTIONNEMENT CORRIGÉ:
    
    • Migration INSTANTANÉE dès que conditions remplies ET cooldown terminé
    • COOLDOWN de 3 MINUTES (180s) après chaque migration
    • PAS de timer supplémentaire pour le retour !
    • Migration immédiate vers topologie 1 dès que trafic < 5 après cooldown
    
    ▸ Terminal 1: Lancer le monitoring
    ▸ Terminal 2: Bombarder avec des requêtes
      while true; do 
        kubectl exec -n iot-topology deployment/device-gf1-1 -- wget -qO- http://iot-gateway-final-1:8281/health > /dev/null 2>&1
        sleep 0.1
      done
    """)
    
    while True:
        print("\n" + "="*60)
        print("MENU PRINCIPAL")
        print("="*60)
        print("""
    1. 🚀 Lancer le monitoring (instantané corrigé)
    2. 🔄 Reset manuel vers topologie 1
    3. 📊 Voir configuration
    0. ❌ Quitter
        """)
        
        choix = input("Votre choix (0-3): ")
        
        if choix == "1":
            monitoring_loop()
        elif choix == "2":
            if current_topology == "modifiee" and not migration_in_progress:
                migrer_vers_topologie1()
            elif migration_in_progress:
                print("⏳ Migration en cours, veuillez patienter...")
            else:
                print("✅ Déjà en topologie nominale")
        elif choix == "3":
            print(f"\n📊 CONFIGURATION:")
            print(f"   • Cooldown: {COOLDOWN_DURATION} secondes (3 minutes)")
            print(f"   • Migration: INSTANTANÉE")
            print(f"   • Topologie 1 → 2: QPS > {THRESHOLDS['gf1_qps_critical']} req/s")
            print(f"   • Topologie 2 → 1: QPS < {THRESHOLDS['gf1_qps_normal']} req/s")
            print(f"   • Topologie actuelle: {current_topology}")
        elif choix == "0":
            print("👋 Au revoir!")
            break
        else:   
            print("❌ Choix invalide")