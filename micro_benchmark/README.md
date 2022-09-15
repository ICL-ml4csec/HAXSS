To run the micro benchmark in a docker container run the following command from this directory:

	docker run --name haxss_mb -d -p 8000:80 -v $(pwd):/var/www/html php:apache


