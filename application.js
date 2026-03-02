/**
 *  Author: Samir MEDJIAH medjiah@laas.fr
 *  File : application.js - CORRIGÉ
 *  Version : 0.3.0
 */

var express = require('express')
var app = express()
app.use(express.json())

var request = require('request');

var argv = require('yargs').argv;

// --remote_ip
// --remote_port
// --device_name
// --send_period
var REMOTE_ENDPOINT = {
    IP: argv.remote_ip,
    PORT: argv.remote_port
};
var DATA_PERIOD = parseInt(argv.send_period) || 5000;
var TARGET_DEVICE = argv.device_name || 'iot-device';

function retrieveData() {
    var uri = 'http://' + REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT + '/device/' + TARGET_DEVICE + '/latest';
    
    console.log('Requesting data from:', uri);
    request({
        method: 'GET',
        uri: uri,
        json: true,
        timeout: 5000
    }, function(error, response, respBody) {
        if (error) {
            console.error('Retrieve data error:', error.code || error.message);
        } else if (response.statusCode === 200) {
            console.log('Latest data received:', respBody);
        } else if (response.statusCode === 404) {
            console.log('No data available for device:', TARGET_DEVICE);
        } else {
            console.log('Response status:', response.statusCode);
        }
    });
}

// Health endpoint for Kiali
app.get('/health', function(req, res) {
    res.sendStatus(200);
});

// Status endpoint
app.get('/status', function(req, res) {
    res.status(200).send({
        remote: REMOTE_ENDPOINT,
        target: TARGET_DEVICE,
        period: DATA_PERIOD,
        status: 'running'
    });
});

// Start server
app.listen(8081, function() {
    console.log('iot-application listening on port 8081');
    console.log('Target server:', REMOTE_ENDPOINT.IP + ':' + REMOTE_ENDPOINT.PORT);
    console.log('Target device:', TARGET_DEVICE);
    console.log('Polling period:', DATA_PERIOD, 'ms');
    
    // Wait for services to be ready
    setTimeout(function() {
        console.log('Starting data retrieval...');
        retrieveData();
        setInterval(retrieveData, DATA_PERIOD);
    }, 20000);
});