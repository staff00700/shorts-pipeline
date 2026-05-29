#!/bin/bash
cd /opt/projects/shorts-pipeline
export PORT=5050
exec ./venv/bin/python3 web_admin.py
