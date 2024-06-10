#!/bin/sh
# Use this to install software packages
sudo yum install -y httpd
sudo systemctl enable httpd
sudo systemctl start httpd
