#!/usr/bin/env python3
import requests
import json

def test_prometheus_connection():
    """Test simple de connexion à Prometheus"""
    
    # Ton port actuel (9090 ou 42311 selon ce qui marche)
    PORT = 9090
    
    print(f"🔍 Test de connexion à Prometheus sur le port {PORT}")
    print("="*50)
    
    # Test 1: Vérifier si le serveur répond
    try:
        url = f"http://localhost:{PORT}/api/v1/query"
        response = requests.get(url, timeout=3)
        print(f"✅ Serveur répond: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Serveur ne répond pas: {e}")
        return
    
    # Test 2: Requête simple 'up' (combien de cibles sont actives)
    try:
        query = "up"
        response = requests.get(url, params={'query': query}, timeout=5)
        data = response.json()
        
        results = data.get('data', {}).get('result', [])
        print(f"✅ Requête 'up' réussie: {len(results)} cibles trouvées")
        
        # Affiche les 3 premières cibles
        for i, result in enumerate(results[:3]):
            metric = result.get('metric', {})
            job = metric.get('job', 'inconnu')
            instance = metric.get('instance', 'inconnue')
            value = result.get('value', [0, 0])[1]
            print(f"   • {job} / {instance}: {value}")
            
    except Exception as e:
        print(f"❌ Erreur requête 'up': {e}")
    
    # Test 3: Requête spécifique à ton namespace
    try:
        query = f'sum(rate(istio_requests_total{{namespace="iot-topology"}}[1m]))'
        response = requests.get(url, params={'query': query}, timeout=5)
        data = response.json()
        
        results = data.get('data', {}).get('result', [])
        if results:
            value = results[0].get('value', [0, 0])[1]
            print(f"✅ Trafic iot-topology détecté: {float(value):.2f} req/s")
        else:
            print(f"⚠️  Aucun trafic dans iot-topology (peut-être normal)")
            
    except Exception as e:
        print(f"❌ Erreur requête trafic: {e}")
    
    # Test 4: Vérifier les métriques de GF1 spécifiquement
    try:
        query = f'sum(rate(istio_requests_total{{namespace="iot-topology", destination_workload="iot-gateway-final-1"}}[1m]))'
        response = requests.get(url, params={'query': query}, timeout=5)
        data = response.json()
        
        results = data.get('data', {}).get('result', [])
        if results:
            value = results[0].get('value', [0, 0])[1]
            print(f"✅ Trafic sur GF1: {float(value):.2f} req/s")
        else:
            print(f"⚠️  Aucun trafic sur GF1")
            
    except Exception as e:
        print(f"❌ Erreur requête GF1: {e}")
    
    print("\n" + "="*50)
    print("Test terminé!")

if __name__ == "__main__":
    test_prometheus_connection()
