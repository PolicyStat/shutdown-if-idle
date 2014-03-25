shutdown-if-idle
================

Shutdown machine if considered idle

Installation 
------------

```bash
pip install -e setup.py
pip install -r test_requirements.txt
```

Running Tests
-------------

```bash
./run_tests.py
```

Uses
----

Lets say that you are using Jenkins with slaves provisioned using AWS spot instances, and you want to be able to control when those slaves get shut down. At the begining of each test you can write a file to `/tmp/_idle_quiet_timer/` that has a `.log` file extension with an integer in it. Say we have:

```
/tmp/_idle_quiet_timer/foo.log
  -> 5
```

If the last modified date of foo.log is shorter than 5 minuets ago then the machine is considered busy. If the last modified date of foo.log is over 5 minuets we considered that job timed out. With the AWS EC2 instances you pay for a full hour even if you do not use that whole our. As such, if the slave only has a 10 minute up-time then there is no point in killing the box. However, if you are on minute 58 and considered idle, it is likely that shutting down the box is a correct action. As such the `shutdown-if-idle` script will shutdown the box.
