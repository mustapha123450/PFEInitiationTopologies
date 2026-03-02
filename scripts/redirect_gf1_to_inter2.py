#!/usr/bin/env python3
"""
SCRIPT DE GESTION D'ARCHITECTURE IOT - VERSION CORRIGÉE
Avec les nouveaux noms : inter-1, inter-2, gwi1, gwi2

OPTION 1 - Architecture modifiée
    GF1 ──► inter-2 ──┐
                       ├──► server
    GF2 ──► inter-1 ──┘
    GF3 ──► inter-1 ──┘
    (inter-1 et inter-2 envoient tous deux vers server)

OPTION 2 - Architecture nominale
    GF1 ──┐
    GF2 ──┼──► inter-1 ──► server
    GF3 ──┘
    (inter-2 existe mais n'est pas utilisé)
"""

import requests
import subprocess
import json
import time
import sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================
# FONCTIONS UTILITAIRES
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

def check_inter2_exists():
    """Vérifie que gateway-inter-2 existe"""
    try:
        result = subprocess.run(
            "kubectl get svc -n iot-topology iot-gateway-inter-2",
            shell=True, capture_output=True, text=True
        )
        return result.returncode == 0
    except:
        return False

def check_inter1_exists():
    """Vérifie que gateway-inter-1 existe"""
    try:
        result = subprocess.run(
            "kubectl get svc -n iot-topology iot-gateway-inter-1",
            shell=True, capture_output=True, text=True
        )
        return result.returncode == 0
    except:
        return False

def delete_all_virtualservices(api_server, token):
    """Supprime TOUTES les règles Istio"""
    print("\n🗑️  Suppression de toutes les règles existantes...")
    url = f"{api_server}/apis/networking.istio.io/v1/namespaces/iot-topology/virtualservices"
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            items = response.json().get('items', [])
            if items:
                for vs in items:
                    name = vs['metadata']['name']
                    print(f"   → Suppression de {name}")
                    requests.delete(f"{url}/{name}", headers=headers, verify=False)
                    time.sleep(0.5)
                print(f"✅ {len(items)} règle(s) supprimée(s)")
            else:
                print("   ℹ️  Aucune règle à supprimer")
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def show_current_status(api_server, token):
    """Affiche l'état actuel des règles"""
    url = f"{api_server}/apis/networking.istio.io/v1/namespaces/iot-topology/virtualservices"
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            items = response.json().get('items', [])
            if items:
                print("\n📊 RÈGLES ACTUELLEMENT ACTIVES:")
                for vs in items:
                    name = vs['metadata']['name']
                    print(f"   • {name}")
            else:
                print("\n📊 État actuel: Architecture nominale (aucune règle)")
        return items
    except:
        return None

# =============================================
# OPTION 1 - ARCHITECTURE MODIFIÉE
# =============================================
def architecture_modifiee():
    """GF1→inter-2, GF2→inter-1, GF3→inter-1"""
    
    print("="*80)
    print("🏗️  OPTION 1 - ARCHITECTURE MODIFIÉE")
    print("="*80)
    print("""
    Configuration appliquée :
    
    GF1 ──► inter-2 ──┐
                       ├──► server
    GF2 ──► inter-1 ──┘
    GF3 ──► inter-1 ──┘
    
    (inter-1 et inter-2 envoient tous deux vers server)
    """)
    
    # Vérifier que inter-2 existe
    print("\n📋 Vérification de gateway-inter-2...")
    if not check_inter2_exists():
        print("❌ gateway-inter-2 n'existe pas !")
        print("   Lancez: kubectl apply -f k8s/02-gateway-inter-2.yaml")
        sys.exit(1)
    print("✅ gateway-inter-2 trouvé")
    
    # Vérifier que inter-1 existe
    if not check_inter1_exists():
        print("⚠️  gateway-inter-1 n'existe pas !")
        print("   Lancez: kubectl apply -f k8s/02-gateway-inter-1.yaml")
        print("   Continuation quand même...")
    
    # Connexion API
    print("\n📋 Connexion à l'API Kubernetes...")
    api_server, token = get_api_info()
    print("✅ Connecté")
    
    # Afficher état actuel
    show_current_status(api_server, token)
    
    # Supprimer toutes les anciennes règles
    delete_all_virtualservices(api_server, token)
    time.sleep(2)
    
    # Créer la nouvelle règle
    print("\n📋 Création de l'architecture modifiée...")
    
    new_config = {
        "apiVersion": "networking.istio.io/v1",
        "kind": "VirtualService",
        "metadata": {
            "name": "archi-modifiee",
            "namespace": "iot-topology"
        },
        "spec": {
            "hosts": [
                "iot-gateway-inter-1.iot-topology.svc.cluster.local"  # ← Changé !
            ],
            "http": [
                {
                    # Règle 1: GF1 → inter-2
                    "match": [
                        {
                            "sourceLabels": {
                                "app": "iot-gateway-final",
                                "gateway-id": "gf1"
                            }
                        }
                    ],
                    "route": [
                        {
                            "destination": {
                                "host": "iot-gateway-inter-2.iot-topology.svc.cluster.local",
                                "port": {
                                    "number": 8182
                                }
                            },
                            "weight": 100
                        }
                    ]
                },
                {
                    # Règle 2: GF2 → inter-1
                    "match": [
                        {
                            "sourceLabels": {
                                "app": "iot-gateway-final",
                                "gateway-id": "gf2"
                            }
                        }
                    ],
                    "route": [
                        {
                            "destination": {
                                "host": "iot-gateway-inter-1.iot-topology.svc.cluster.local",  # ← Changé !
                                "port": {
                                    "number": 8181
                                }
                            },
                            "weight": 100
                        }
                    ]
                },
                {
                    # Règle 3: GF3 → inter-1
                    "match": [
                        {
                            "sourceLabels": {
                                "app": "iot-gateway-final",
                                "gateway-id": "gf3"
                            }
                        }
                    ],
                    "route": [
                        {
                            "destination": {
                                "host": "iot-gateway-inter-1.iot-topology.svc.cluster.local",  # ← Changé !
                                "port": {
                                    "number": 8181
                                }
                            },
                            "weight": 100
                        }
                    ]
                }
            ]
        }
    }
    
    base_url = f"{api_server}/apis/networking.istio.io/v1/namespaces/iot-topology/virtualservices"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(base_url, headers=headers, json=new_config, verify=False)
        
        if response.status_code == 201:
            print("✅ SUCCÈS ! Architecture modifiée créée")
        else:
            print(f"❌ Erreur {response.status_code}: {response.text}")
            return
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return
    
    print("\n" + "="*80)
    print("🎯 ARCHITECTURE MODIFIÉE - ACTIVE")
    print("="*80)
    print("""
    ✅ FLUX ÉTABLI :
    
    GF1 ──► inter-2 ──┐
                       ├──► SERVER
    GF2 ──► inter-1 ──┘
    GF3 ──► inter-1 ──┘
    
    ✅ inter-1 → server (par son YAML)
    ✅ inter-2 → server (par son YAML)
    """)
    
    print("\n🔍 TESTS DE VÉRIFICATION :")
    print("-"*60)
    print("1️⃣  GF1 → inter-2 (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-final-1 -- wget -qO- http://iot-gateway-inter-2:8182/ping")
    print("\n2️⃣  GF2 → inter-1 (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-final-2 -- wget -qO- http://iot-gateway-inter-1:8181/ping")  # ← Changé !
    print("\n3️⃣  GF3 → inter-1 (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-final-3 -- wget -qO- http://iot-gateway-inter-1:8181/ping")  # ← Changé !
    print("\n4️⃣  inter-1 → server (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-inter-1 -- wget -qO- http://iot-server:8080/ping")  # ← Changé !
    print("\n5️⃣  inter-2 → server (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-inter-2 -- wget -qO- http://iot-server:8080/ping")
    print("\n6️⃣  Voir la règle créée:")
    print("   kubectl get virtualservice -n iot-topology archi-modifiee -o yaml")

# =============================================
# OPTION 2 - ARCHITECTURE NOMINALE
# =============================================
def architecture_nominale():
    """Retour à la configuration des YAML : tous les GF → inter-1 → server"""
    
    print("="*80)
    print("🏗️  OPTION 2 - ARCHITECTURE NOMINALE")
    print("="*80)
    print("""
    Configuration appliquée :
    
    GF1 ──┐
    GF2 ──┼──► inter-1 ──► server
    GF3 ──┘
    
    (inter-2 existe mais n'est pas utilisé)
    """)
    
    # Connexion API
    print("\n📋 Connexion à l'API Kubernetes...")
    api_server, token = get_api_info()
    print("✅ Connecté")
    
    # Afficher état actuel
    show_current_status(api_server, token)
    
    # Supprimer toutes les règles
    delete_all_virtualservices(api_server, token)
    
    print("\n" + "="*80)
    print("🎯 ARCHITECTURE NOMINALE - ACTIVE")
    print("="*80)
    print("""
    ✅ Retour à la configuration des YAML :
    
    GF1 ──┐
    GF2 ──┼──► inter-1 ──► server
    GF3 ──┘
    
    ✅ inter-1 → server (par son YAML)
    ✅ inter-2 → server (par son YAML - mais non utilisé)
    """)
    
    print("\n🔍 TESTS DE VÉRIFICATION :")
    print("-"*60)
    print("1️⃣  GF1 → inter-1 (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-final-1 -- wget -qO- http://iot-gateway-inter-1:8181/ping")  # ← Changé !
    print("\n2️⃣  GF2 → inter-1 (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-final-2 -- wget -qO- http://iot-gateway-inter-1:8181/ping")  # ← Changé !
    print("\n3️⃣  GF3 → inter-1 (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-final-3 -- wget -qO- http://iot-gateway-inter-1:8181/ping")  # ← Changé !
    print("\n4️⃣  inter-1 → server (doit réussir):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-inter-1 -- wget -qO- http://iot-server:8080/ping")  # ← Changé !
    print("\n5️⃣  inter-2 → server (doit réussir - mais non utilisé):")
    print("   kubectl exec -n iot-topology deployment/iot-gateway-inter-2 -- wget -qO- http://iot-server:8080/ping")
    print("\n6️⃣  Vérification qu'aucune règle n'existe:")
    print("   kubectl get virtualservice -n iot-topology")

# =============================================
# MENU PRINCIPAL
# =============================================
if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 GESTIONNAIRE D'ARCHITECTURE IOT")
    print("="*80)
    
    # Afficher l'état actuel
    try:
        api_server, token = get_api_info()
        show_current_status(api_server, token)
    except:
        print("\n⚠️  Impossible de se connecter à l'API Kubernetes")
        print("   Vérifiez que votre cluster est accessible")
    
    print("\n" + "="*80)
    print("OPTIONS DISPONIBLES:")
    print("="*80)
    print("""
    OPTION 1 - ARCHITECTURE MODIFIÉE
    ─────────────────────────────────
    GF1 ──► inter-2 ──┐
                       ├──► server
    GF2 ──► inter-1 ──┘
    GF3 ──► inter-1 ──┘
    
    OPTION 2 - ARCHITECTURE NOMINALE
    ─────────────────────────────────
    GF1 ──┐
    GF2 ──┼──► inter-1 ──► server
    GF3 ──┘
    """)
    print("-"*80)
    
    choix = input("Votre choix (1 ou 2): ")
    
    if choix == "1":
        architecture_modifiee()
    elif choix == "2":
        architecture_nominale()
    else:
        print("❌ Choix invalide")