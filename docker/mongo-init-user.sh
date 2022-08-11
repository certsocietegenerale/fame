#!/bin/sh
mongosh --eval "
    disableTelemetry();
    db.createUser({
      user: process.env['MONGODB_USERNAME'],
      pwd: process.env['MONGODB_PASSWORD'],
      roles: ['readWrite'],
    });" -- "$MONGO_INITDB_DATABASE"
