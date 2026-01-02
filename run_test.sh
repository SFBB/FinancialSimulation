#!/usr/bin/bash

source venv/bin/activate

python3 -m test.test_realism
python3 -m test.reproduce_issue
python3 -m test.test_moutai
python3 -m test.check_market_trend
python3 -m test.test_data_loader
python3 -m test.test_look_ahead_fix
python3 -m test.test_tech_trinity
python3 -m test.test_super_six
