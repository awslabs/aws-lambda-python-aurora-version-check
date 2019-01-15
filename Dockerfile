FROM amazonlinux
RUN yum install -y python3-pip python36 python36-setuptools zip && yum clean all
COPY src /build
RUN pip3 install -r /build/requirements.txt -t /build/requirements/
WORKDIR /build
CMD sh build_package.sh
