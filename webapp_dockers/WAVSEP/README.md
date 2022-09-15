To run WAVSEP as a Docker container run these commands from this directory:

	docker build -t wavsep .
	docker run -p 8081:80 --name wavsep -d wavsep
