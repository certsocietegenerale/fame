#!/bin/sh
#mongosh admin --eval "
#    disableTelemetry();
#    db.createUser({
#      user: process.env['MONGODB_ROOT_USERNAME'],
#      pwd: process.env['MONGODB_ROOT_PASSWORD'],
#      roles: ['readWriteAnyDatabase'],
#    });"

mongosh --eval "
    disableTelemetry();
    db.createUser({
      user: process.env['MONGODB_USERNAME'],
      pwd: process.env['MONGODB_PASSWORD'],
      roles: ['readWrite'],
    });" -- "$MONGO_INITDB_DATABASE"
