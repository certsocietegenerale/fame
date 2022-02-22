db.createUser({
    user: _getEnv("MONGODB_USERNAME"),
    pwd: _getEnv("MONGODB_PASSWORD"),
    roles: [ { role: 'readWrite', db: _getEnv("MONGO_INITDB_DATABASE") } ]
})
