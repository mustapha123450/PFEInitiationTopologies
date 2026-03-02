/**
 *  Author: Samir MEDJIAH medjiah@laas.fr
 *  File : gateway.js - CORRIGÉ FINAL
 *  Version : 0.4.0
 */

var express = require('express')
var app = express()
app.use(express.json())

var request = require('request');
const si = require('systeminformation');
var argv = require('yargs').argv;

// --local_ip
// --local_port
// --local_name
// --remote_ip
// --remote_port
// --remote_name
var LOCAL_ENDPOINT = {
    IP: argv.local_ip,
    PORT: argv.local_port,
    NAME: argv.local_name
};
var REMOTE_ENDPOINT = {
    IP: argv.remote_ip,
    PORT: argv.remote_port,
    NAME: argv.remote_name
};

const E_OK = 200;
const E_CREATED = 201;
const E_NOT_FOUND = 404;
const E_ALREADY_EXIST = 500;

var db = {
    gateways: new Map()
};

function addNewGateway(gw) {
    var res = -1;
    if (!db.gateways.get(gw.Name)) {
        db.gateways.set(gw.Name, gw);
        res = 0;
        console.log('✅ Gateway registered locally:', gw.Name);
    }
    return res;
}

function doPOST(uri, body, onResponse) {
    request({
        method: 'POST',
        uri: uri,
        json: body,
        timeout: 5000
    }, onResponse);
}

function register() {
    var registerData = {
        Name: LOCAL_ENDPOINT.NAME,
        PoC: 'http://' + LOCAL_ENDPOINT.NAME + '.' + process.env.NAMESPACE + '.svc.cluster.local:' + LOCAL_ENDPOINT.PORT
    };
    
    console.log('📝 Registering to:', 'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/gateways/register');
    doPOST(
        'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/gateways/register',
        registerData,
        function(error, response, respBody) {
            if (error) {
                console.error('❌ Registration error:', error.code || error.message);
                setTimeout(register, 10000);
            } else {
                console.log('✅ Registration successful:', LOCAL_ENDPOINT.NAME, '->', REMOTE_ENDPOINT.NAME);
            }
        }
    );
}

// Route pour enregistrement des gateways
app.post('/gateways/register', function(req, res) {
    console.log('📝 Gateway register request from:', req.body.Name);
    var result = addNewGateway(req.body);
    if (result === 0)
        res.sendStatus(E_CREATED);
    else
        res.sendStatus(E_ALREADY_EXIST);
});

// Route pour enregistrement des devices - FORWARD vers remote
app.post('/devices/register', function(req, res) {
    console.log('📱 Forwarding device registration:', req.body.Name);
    doPOST(
        'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/devices/register',
        req.body,
        function(error, response, respBody) {
            if (error) {
                console.error('❌ Forward registration error:', error.code || error.message);
                res.sendStatus(500);
            } else {
                console.log('✅ Device registration forwarded to', REMOTE_ENDPOINT.NAME);
                res.sendStatus(E_OK);
            }
        }
    );
});

// ROUTE CRITIQUE - Données des devices - FORWARD vers remote
app.post('/device/:dev/data', function(req, res) {
    console.log('📊 Forwarding data from device:', req.params.dev, 'Data:', req.body.Data);
    
    // Ajouter timestamp de réception
    req.body.ReceptionTime = Date.now();
    
    doPOST(
        'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/device/' + req.params.dev + '/data',
        req.body,
        function(error, response, respBody) {
            if (error) {
                console.error('❌ Forward data error:', error.code || error.message);
                res.sendStatus(500);
            } else {
                console.log('✅ Data forwarded to', REMOTE_ENDPOINT.NAME);
                res.sendStatus(E_OK);
            }
        }
    );
});

// Route ping pour tests
app.get('/ping', function(req, res) {
    res.status(E_OK).send({ pong: Date.now() });
});

// Route health
app.get('/health', function(req, res) {
    si.currentLoad((d) => {
        res.status(E_OK).send(JSON.stringify(d));
    });
});

// Liste des gateways
app.get('/gateways', function(req, res) {
    let resObj = [];
    db.gateways.forEach((v, k) => resObj.push(v));
    res.send(resObj);
});

// Détail d'un gateway
app.get('/gateway/:gw', function(req, res) {
    var gw = req.params.gw;
    var gateway = db.gateways.get(gw);
    gateway ? res.status(E_OK).send(JSON.stringify(gateway)) : res.sendStatus(E_NOT_FOUND);
});

// Set namespace
process.env.NAMESPACE = 'iot-topology';

// Démarrage
app.listen(LOCAL_ENDPOINT.PORT, function() {
    console.log('🚀 ' + LOCAL_ENDPOINT.NAME + ' listening on port: ' + LOCAL_ENDPOINT.PORT);
    console.log('🎯 Remote target:', REMOTE_ENDPOINT.NAME, '(' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + ')');
    
    // Register with parent gateway after 10 seconds
    setTimeout(register, 10000);
});