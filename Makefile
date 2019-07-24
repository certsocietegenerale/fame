.DEFAULT_GOAL := all

mongo:
	docker build -t fame-mongo docker/mongo/

base:
	docker build -t fame-base -f Dockerfile.base .

web: base
	docker build -t fame-web -f Dockerfile.web .

worker: base
	docker build -t fame-worker -f Dockerfile.worker .

all: mongo base web worker
