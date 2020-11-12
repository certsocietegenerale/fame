"use fame";
db.createUser({
    user: "fame",
    pwd: "super-secret-password",
    roles: [
        { role: "readWrite", db: "fame" },
        { role: "dbOwner", db: "fame" }
    ]
});
