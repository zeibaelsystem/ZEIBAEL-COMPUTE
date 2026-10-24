FROM alpine:3.21
COPY marker.txt /opt/marker.txt
CMD ["sh", "-c", "grep -q ZEIBAEL_DOCKER_OK /opt/marker.txt && echo ZEIBAEL_DOCKER_OK"]
