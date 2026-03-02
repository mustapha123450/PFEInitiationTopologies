/**
 *  Author: Samir MEDJIAH medjiah@laas.fr
 *  File : device.js - CORRIGÉ
 *  Version : 0.3.0
 */

var express = require('express')
var app = express()
app.use(express.json())

var request = require('request');

var argv = require('yargs').argv;

// --local_ip
// --local_port
// --local_name
// --remote_ip
// --remote_port
// --remote_name
// --send_period
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

var DATA_PERIOD = parseInt(argv.send_period) || 3000;

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
    
    console.log('Registering device to:', 'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/devices/register');
    doPOST(
        'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/devices/register',
        registerData,
        function(error, response, respBody) {
            if (error) {
                console.error('Registration error:', error.code || error.message);
                setTimeout(register, 10000);
            } else {
                console.log('Device registered successfully:', LOCAL_ENDPOINT.NAME);
            }
        }
    );
}

var dataItem = 0;
function sendData() {
    var data = {
        Name: LOCAL_ENDPOINT.NAME,
        Data: dataItem++,
        CreationTime: Date.now(),
        ReceptionTime: null
    };
    
    console.log('Sending data:', dataItem - 1, 'to', REMOTE_ENDPOINT.IP);
    doPOST(
        'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/device/' + LOCAL_ENDPOINT.NAME + '/data',
        data,
        function(error, response, respBody) {
            if (error) {
                console.error('Send data error:', error.code || error.message);
            } else {
                console.log('Data sent successfully:', dataItem - 1);
            }
        }
    );
}

// Health endpoint for Kiali
app.get('/health', function(req, res) {
    res.sendStatus(200);
});

// Get device info
app.get('/info', function(req, res) {
    res.status(200).send({
        name: LOCAL_ENDPOINT.NAME,
        ip: LOCAL_ENDPOINT.IP,
        port: LOCAL_ENDPOINT.PORT,
        remote: REMOTE_ENDPOINT
    });
});

// Set namespace
process.env.NAMESPACE = 'iot-topology';

// Start server
app.listen(LOCAL_ENDPOINT.PORT, function() {
    console.log(LOCAL_ENDPOINT.NAME + ' listening on port: ' + LOCAL_ENDPOINT.PORT);
    
    // Register after 15 seconds
    setTimeout(function() {
        register();
        
        // Start sending data after registration
        setTimeout(function() {
            setInterval(sendData, DATA_PERIOD);
        }, 5000);
    }, 15000);
});