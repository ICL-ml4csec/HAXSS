To run WebSecLab as a Docker container run these commands from this directory:

	docker build -t webseclab .
	docker run -p 8080:8080 --name webseclab -d webseclab
