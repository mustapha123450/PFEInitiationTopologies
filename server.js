/**
 *  Author: Samir MEDJIAH medjiah@laas.fr
 *  File : server.js - CORRIGÉ
 *  Version : 0.3.0
 */

var express = require('express')
var app = express()
app.use(express.json())

var argv = require('yargs').argv;
const si = require('systeminformation');

// --local_ip
// --local_port
// --local_name
var LOCAL_ENDPOINT = {
    IP: argv.local_ip,
    PORT: argv.local_port,
    NAME: argv.local_name
};

const E_OK = 200;
const E_CREATED = 201;
const E_FORBIDDEN = 403;
const E_NOT_FOUND = 404;
const E_ALREADY_EXIST = 500;

var db = {
    devices: new Map(),
    data: new Map(),
    gateways: new Map()
};

function addNewDevice(dev) {
    var result = -1;
    if (!db.devices.get(dev.Name)) {
        db.devices.set(dev.Name, dev);
        db.data.set(dev.Name, []);
        result = 0;
        console.log('Device registered:', dev.Name);
    }
    return result;
}

function addNewGateway(gw) {
    var result = -1;
    if (!db.gateways.get(gw.Name)) {
        db.gateways.set(gw.Name, gw);
        result = 0;
        console.log('Gateway registered:', gw.Name);
    }
    return result;
}

function removeDevice(dev) {
    if (db.devices.get(dev.Name)) {
        db.devices.delete(dev.Name);
        db.data.delete(dev.Name);
        console.log('Device removed:', dev.Name);
    }
}

function removeGateway(gw) {
    if (db.gateways.get(gw.Name)) {
        db.gateways.delete(gw.Name);
        console.log('Gateway removed:', gw.Name);
    }
}

function addDeviceData(dev, data) {
    var result = -1;
    var device = db.devices.get(dev);
    if (device) {
        data.ReceptionTime = Date.now();
        db.data.get(dev).push(data);
        result = 0;
        console.log('Data added for device:', dev, 'Data count:', db.data.get(dev).length);
    }
    return result;
}

app.get('/devices', function(req, res) {
    let resObj = [];
    db.devices.forEach((v, k) => {
        resObj.push(v);
    });
    res.status(E_OK).send(resObj);
});

app.get('/device/:dev', function(req, res) {
    var dev = req.params.dev;
    var device = db.devices.get(dev);
    if (device)
        res.status(E_OK).send(JSON.stringify(device));
    else
        res.sendStatus(E_NOT_FOUND);
});

app.post('/device/:dev/data', function(req, res) {
    var dev = req.params.dev;
    var result = addDeviceData(dev, req.body);
    if (result === 0)
        res.sendStatus(E_CREATED);
    else
        res.sendStatus(E_NOT_FOUND);
});

app.get('/device/:dev/data', function(req, res) {
    var dev = req.params.dev;
    var device = db.devices.get(dev);
    if (device) {
        var data = db.data.get(dev);
        if (data && data.length > 0) {
            let resObj = [];
            data.forEach((v, k) => {
                resObj.push(v);
            });
            res.status(E_OK).send(JSON.stringify(resObj));
        } else {
            res.sendStatus(E_NOT_FOUND);
        }
    } else {
        res.sendStatus(E_NOT_FOUND);
    }
});

app.get('/device/:dev/latest', function(req, res) {
    var dev = req.params.dev;
    var device = db.devices.get(dev);
    if (device) {
        var data = db.data.get(dev);
        if (data && data.length > 0) {
            let resObj = data[data.length - 1];
            res.status(E_OK).send(JSON.stringify(resObj));
        } else {
            res.sendStatus(E_NOT_FOUND);
        }
    } else {
        res.sendStatus(E_NOT_FOUND);
    }
});

app.post('/devices/register', function(req, res) {
    console.log('Device registration request:', req.body);
    var result = addNewDevice(req.body);
    if (result === 0)
        res.sendStatus(E_CREATED);
    else
        res.sendStatus(E_ALREADY_EXIST);
});

app.get('/gateways', function(req, res) {
    let resObj = [];
    db.gateways.forEach((v, k) => {
        resObj.push(v);
    });
    res.send(resObj);
});

app.get('/gateway/:gw', function(req, res) {
    var gw = req.params.gw;
    var gateway = db.gateways.get(gw);
    if (gateway)
        res.status(E_OK).send(JSON.stringify(gateway));
    else
        res.sendStatus(E_NOT_FOUND);
});

app.post('/gateways/register', function(req, res) {
    console.log('Gateway registration request:', req.body);
    var result = addNewGateway(req.body);
    if (result === 0)
        res.sendStatus(E_CREATED);
    else
        res.sendStatus(E_ALREADY_EXIST);
});

app.get('/ping', function(req, res) {
    res.status(E_OK).send({ pong: Date.now() });
});

app.get('/health', function(req, res) {
    si.currentLoad((d) => {
        res.status(E_OK).send(JSON.stringify(d));
    });
});

app.listen(LOCAL_ENDPOINT.PORT, function() {
    console.log(LOCAL_ENDPOINT.NAME + ' listening on port: ' + LOCAL_ENDPOINT.PORT);
});