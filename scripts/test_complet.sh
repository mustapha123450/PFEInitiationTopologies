#!/bin/bash
echo "========================================="
echo "🔍 TEST COMPLET DE L'ARCHITECTURE IOT"
echo "========================================="
echo ""

# 1. TEST SERVER
echo "1️⃣  SERVER"
echo "------------------------"
kubectl exec -n iot-topology deployment/iot-server -- wget -qO- http://localhost:8080/ping && echo "   ✅ Server OK" || echo "   ❌ Server FAIL"
echo ""

# 2. TEST GATEWAYS INTER
echo "2️⃣  GATEWAYS INTERMÉDIAIRES"
echo "------------------------"
# inter-1
kubectl exec -n iot-topology deployment/iot-gateway-inter -- wget -qO- http://localhost:8181/ping && echo "   ✅ inter-1 OK" || echo "   ❌ inter-1 FAIL"
# inter-2
kubectl exec -n iot-topology deployment/iot-gateway-inter-2 -- wget -qO- http://localhost:8182/ping && echo "   ✅ inter-2 OK" || echo "   ❌ inter-2 FAIL"
echo ""

# 3. INTER → SERVER
echo "3️⃣  CONNEXIONS INTER → SERVER"
echo "------------------------"
# inter-1 → server
kubectl exec -n iot-topology deployment/iot-gateway-inter -- wget -qO- http://iot-server:8080/ping && echo "   ✅ inter-1 → server OK" || echo "   ❌ inter-1 → server FAIL"
# inter-2 → server
kubectl exec -n iot-topology deployment/iot-gateway-inter-2 -- wget -qO- http://iot-server:8080/ping && echo "   ✅ inter-2 → server OK" || echo "   ❌ inter-2 → server FAIL"
echo ""

# 4. TEST GATEWAYS FINAL
echo "4️⃣  GATEWAYS FINALES"
echo "------------------------"
# GF1
kubectl exec -n iot-topology deployment/iot-gateway-final-1 -- wget -qO- http://localhost:8281/ping && echo "   ✅ GF1 OK" || echo "   ❌ GF1 FAIL"
# GF2
kubectl exec -n iot-topology deployment/iot-gateway-final-2 -- wget -qO- http://localhost:8282/ping && echo "   ✅ GF2 OK" || echo "   ❌ GF2 FAIL"
# GF3
kubectl exec -n iot-topology deployment/iot-gateway-final-3 -- wget -qO- http://localhost:8283/ping && echo "   ✅ GF3 OK" || echo "   ❌ GF3 FAIL"
echo ""

# 5. GF → INTER (selon les règles)
echo "5️⃣  CONNEXIONS GF → INTER"
echo "------------------------"
# GF1 → inter-2 (doit réussir)
kubectl exec -n iot-topology deployment/iot-gateway-final-1 -- wget -qO- http://iot-gateway-inter-2:8182/ping && echo "   ✅ GF1 → inter-2 OK" || echo "   ❌ GF1 → inter-2 FAIL"
# GF2 → inter-1 (doit réussir)
kubectl exec -n iot-topology deployment/iot-gateway-final-2 -- wget -qO- http://iot-gateway-inter:8181/ping && echo "   ✅ GF2 → inter-1 OK" || echo "   ❌ GF2 → inter-1 FAIL"
# GF3 → inter-1 (doit réussir)
kubectl exec -n iot-topology deployment/iot-gateway-final-3 -- wget -qO- http://iot-gateway-inter:8181/ping && echo "   ✅ GF3 → inter-1 OK" || echo "   ❌ GF3 → inter-1 FAIL"
echo ""

# 6. TEST DES APPLICATIONS
echo "6️⃣  APPLICATIONS"
echo "------------------------"
# app-zone1
kubectl exec -n iot-topology deployment/iot-application-zone1 -- wget -qO- http://localhost:8081/health && echo "   ✅ app-zone1 OK" || echo "   ❌ app-zone1 FAIL"
# app-zone2
kubectl exec -n iot-topology deployment/iot-application-zone2 -- wget -qO- http://localhost:8081/health && echo "   ✅ app-zone2 OK" || echo "   ❌ app-zone2 FAIL"
# app-zone3
kubectl exec -n iot-topology deployment/iot-application-zone3 -- wget -qO- http://localhost:8081/health && echo "   ✅ app-zone3 OK" || echo "   ❌ app-zone3 FAIL"
echo ""

# 7. APPLICATIONS → SERVER (récupération des données)
echo "7️⃣  APPLICATIONS → SERVER (DONNÉES)"
echo "------------------------"
# app-zone1 (devrait voir device-gf1-1)
echo "app-zone1:"
kubectl exec -n iot-topology deployment/iot-application-zone1 -- wget -qO- http://iot-server:8080/device/device-gf1-1/latest 2>/dev/null | head -c 100 && echo "..." || echo "   ❌ Pas de données"
# app-zone2 (devrait voir device-gf2-1)
echo -e "\napp-zone2:"
kubectl exec -n iot-topology deployment/iot-application-zone2 -- wget -qO- http://iot-server:8080/device/device-gf2-1/latest 2>/dev/null | head -c 100 && echo "..." || echo "   ❌ Pas de données"
# app-zone3 (devrait voir device-gf3-1)
echo -e "\napp-zone3:"
kubectl exec -n iot-topology deployment/iot-application-zone3 -- wget -qO- http://iot-server:8080/device/device-gf3-1/latest 2>/dev/null | head -c 100 && echo "..." || echo "   ❌ Pas de données"
echo ""

# 8. VÉRIFICATION DES DONNÉES DANS LE SERVER
echo "8️⃣  DONNÉES DANS LE SERVER"
echo "------------------------"
echo "device-gf1-1:"
kubectl exec -n iot-topology deployment/iot-server -- wget -qO- http://localhost:8080/device/device-gf1-1/latest 2>/dev/null | head -c 100 && echo "..."
echo -e "\ndevice-gf2-1:"
kubectl exec -n iot-topology deployment/iot-server -- wget -qO- http://localhost:8080/device/device-gf2-1/latest 2>/dev/null | head -c 100 && echo "..."
echo -e "\ndevice-gf3-1:"
kubectl exec -n iot-topology deployment/iot-server -- wget -qO- http://localhost:8080/device/device-gf3-1/latest 2>/dev/null | head -c 100 && echo "..."

echo ""
echo "========================================="
echo "✅ TEST TERMINÉ"
echo "========================================="
