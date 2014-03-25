#! /usr/bin/env python
"""
Automatically shutdown this cloud server when it's idle in a cost-aware
fashion. Take in to account the fact that some providers (like AWS EC2) charge
you for partial hours, so there's no reason to shutdown early if you've already
paid for the whole hour.

## Using This Script

### Run This Script Every Minute as Root via Cron

### Write a File On Job Start

Write a uniquely-named file to the ``JOB_TRACKING_DIR``
that just contains the number of minutes
that you'd like to wait before considering this a timeout.
The filename should end in ``.log``.

### Delete the Appropriate File On Job End

Clean up the job's file when it finishes.
"""
from __future__ import division

import logging
import math
import os
import time
from collections import namedtuple

DEFAULTS = {
    # The directory that will contain all of the job-specific tracking files
    'JOB_TRACKING_DIR': '/tmp/idle-tracking/',
    # The number of minutes that are locked-in from boot time.
    # For EC2, that's 60 minutes. For GCE, that's 10 minutes.
    'PAID_ON_BOOT_MINUTES': '60',
    # The minimum amount of minutes you can pay for.
    # For EC2, that's 60 minutes. For GCE, that's 1 minute.
    'MINIMUM_PAYMENT_CHUNK_MINUTES': '60',
    # We'll initiate a shutdown this many minutes early,
    # to account for lag from uptime measurements or for delays in registering
    # the shutdown call.
    'SHUTDOWN_SAFETY_MARGIN_MINUTES': '2',
    # Wait this long after all jobs have completed (or timed out) before
    # considering this machine idle and eligible for being shut down
    'IDLE_QUIET_MINUTES': '2',
}

# The job name we'll use to implement the idle quiet period
IDLE_QUIET_JOB_NAME = '_idle_quiet_timer'

JOB_FILE_EXTENSION = '.log'

Jobs = namedtuple(
    'Jobs',
    [
        'name',
        'seconds_running',
        'timeout_threshold_minutes',
        'file_path',
    ],
)

formatter_with_time = logging.Formatter(
    "%(asctime)s|%(levelname)s|%(message)s", "%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter_with_time)

logger = logging.getLogger('inactivity_shutdown')


def _file_name_from_job_name(tracking_dir, job_name):
    return os.path.join(
        tracking_dir,
        "%s%s" % (job_name, JOB_FILE_EXTENSION),
    )


def create_tracking_dir(tracking_dir):
    os.makedirs(tracking_dir)


def _build_job_from_fp(tracking_dir, job_filepath):
    filepath = os.path.join(tracking_dir, job_filepath)

    last_modified_time = os.path.getmtime(filepath)
    seconds_running = time.time() - last_modified_time

    _, filename = os.path.split(filepath)

    with open(filepath, 'r') as f:
        timeout_minutes = float(f.readline().split()[0])

    job_name = os.path.splitext(job_filepath)[0]  # Strip the extension.

    return Jobs(
        name=job_name,
        seconds_running=int(seconds_running),
        timeout_threshold_minutes=int(timeout_minutes),
        file_path=filepath,
    )


def build_jobs_from_dir(tracking_dir):
    jobs = []

    if not os.path.isdir(tracking_dir):
        create_tracking_dir(tracking_dir)

    try:
        job_files = os.listdir(tracking_dir)
    except OSError:
        logger.critical(
            "Problem reading the job-tracking directory: '%s'",
            tracking_dir,
        )
        job_files = []

    for job_filepath in job_files:
        if not job_filepath.endswith(JOB_FILE_EXTENSION):
            logger.info(
                "File doesn't end with %s, skpping: %s",
                JOB_FILE_EXTENSION,
                job_filepath,
            )
            continue

        logger.debug("Parsing job for: %s", job_filepath)
        job = _build_job_from_fp(tracking_dir, job_filepath)
        jobs.append(job)

    return jobs


def remove_timed_out_jobs(jobs):
    running_jobs = []

    running_jobs = [
        job for job in jobs
        if job.seconds_running < (job.timeout_threshold_minutes * 60)
    ]
    jobs_to_terminate = [
        job for job in jobs
        if job.seconds_running >= (job.timeout_threshold_minutes * 60)
    ]
    for job in running_jobs:
        logger.info(
            "Job '%s' still running after %s seconds",
            job.name,
            job.seconds_running,
        )

    for job in jobs_to_terminate:
        logger.info(
            "Job '%s' timed out after %s seconds",
            job.name,
            job.seconds_running,
        )
        os.remove(job.file_path)

    return running_jobs


def is_machine_idle(jobs, idle_quiet_period, tracking_dir):
    were_in_quiet_period = False
    for job in jobs:
        if job.name == IDLE_QUIET_JOB_NAME:
            were_in_quiet_period = True
            logger.info("Previously in the quiet period")
            break

    running_jobs = remove_timed_out_jobs(jobs)

    if running_jobs:
        logger.info("%s jobs still running. Not idle.", len(running_jobs))
        return False

    if were_in_quiet_period:
        # If we were in the quiet period, which has now timed out,
        # we're now actually idle.
        logger.info("No jobs running and quiet period ended. Idle.")
        return True

    # Start the idle quiet period timer
    logger.info("Starting the quiet period. Not yet idle.")
    idle_job_fp = _file_name_from_job_name(tracking_dir, IDLE_QUIET_JOB_NAME)

    with open(idle_job_fp, 'w') as idle_job_f:
        idle_job_f.write(idle_quiet_period)

    return False


def shutdown_saves_money(
    uptime_seconds,
    paid_on_boot_minutes,
    payment_chunk_minutes,
    shutdown_safety_margin,
):
    """
    Decide if shutting down this idle machine will save us money.

    We choose to err on the side of keeping a machine up at 59 minutes, when
    it might have been able to have been shutdown, versus shutting a machine
    down at 60 minutes and 1 second and paying for two hours

    >>> shutdown_saves_money(5*60, 10, 1, 2)
    False
    >>> shutdown_saves_money(6*60, 10, 1, 2)
    True
    >>> shutdown_saves_money(7*60, 10, 1, 2)
    True
    >>> shutdown_saves_money(8*60, 10, 1, 2)
    True
    >>> shutdown_saves_money(9*60, 10, 1, 2)
    True
    >>> shutdown_saves_money(10*60, 10, 1, 2)
    True
    >>> shutdown_saves_money(11*60, 10, 1, 2)
    True
    >>> shutdown_saves_money(55*60, 60, 60, 2)
    False
    >>> shutdown_saves_money(56*60, 60, 60, 2)
    True
    >>> shutdown_saves_money(57*60, 60, 60, 2)
    True
    >>> shutdown_saves_money(58*60, 60, 60, 2)
    False
    >>> shutdown_saves_money(59*60, 60, 60, 2)
    False
    >>> shutdown_saves_money(60*60, 60, 60, 2)
    False
    >>> shutdown_saves_money(115*60, 60, 60, 2)
    False
    >>> shutdown_saves_money(116*60, 60, 60, 2)
    True
    >>> shutdown_saves_money(117*60, 60, 60, 2)
    True
    >>> shutdown_saves_money(118*60, 60, 60, 2)
    False
    >>> shutdown_saves_money(119*60, 60, 60, 2)
    False
    >>> shutdown_saves_money(120*60, 60, 60, 2)
    False
    """
    shutdown_safety_seconds = shutdown_safety_margin * 60
    safe_uptime_seconds = uptime_seconds + shutdown_safety_seconds
    safe_uptime_minutes = safe_uptime_seconds / 60

    def already_paid_from_boot():
        # Give ourselves a shutdown margin for error
        seconds_to_pay = safe_uptime_seconds + shutdown_safety_seconds
        seconds_already_paid = paid_on_boot_minutes * 60

        paid_seconds_left = seconds_already_paid - seconds_to_pay
        if paid_seconds_left > 0:
            logger.debug("%s seconds of paid time left.", paid_seconds_left)
            # Already paid
            return True
        return False

    if already_paid_from_boot():
        logger.info("Idle, but we paid for this time on boot.")
        # We've already paid for this time. Shutting down won't save money.
        return False

    if payment_chunk_minutes <= 2:
        # If the granularity is 2 minutes or under, not worth waiting to
        # shutdown and maybe messing up the timing.
        # Shutdown now.
        return True

    # If we're in the `shutdown_safety_margin` window before needing buy
    # another `payment_chunk_minutes` bloc of time, we should shut down.
    chunks_paid = math.floor(safe_uptime_minutes / payment_chunk_minutes)
    logger.debug("Already paid %s chunks", chunks_paid)
    next_chunk_uptime_seconds = (chunks_paid + 1) * payment_chunk_minutes * 60

    logger.debug("Current uptime seconds: %s", uptime_seconds)
    logger.debug("Next payment chunk: %s", next_chunk_uptime_seconds)

    seconds_until_next_chunk = next_chunk_uptime_seconds - safe_uptime_seconds
    if seconds_until_next_chunk <= shutdown_safety_seconds:
        logger.info(
            "Only %s paid seconds left. Recommending shutdown.",
            seconds_until_next_chunk,
        )
        return True

    return False


def get_uptime_seconds():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])

    return int(uptime_seconds)


def trigger_shutdown():
    msg = "Shutdown by shutdown_if_no_usage.py due to inactivity"
    os.system('/sbin/shutdown -h now "%s"' % msg)


def main(options):
    jobs = build_jobs_from_dir(tracking_dir=options['JOB_TRACKING_DIR'])

    is_idle = is_machine_idle(
        jobs=jobs,
        idle_quiet_period=options['IDLE_QUIET_MINUTES'],
        tracking_dir=options['JOB_TRACKING_DIR'],
    )

    if is_idle:
        uptime_seconds = get_uptime_seconds()
        if shutdown_saves_money(
            uptime_seconds=uptime_seconds,
            paid_on_boot_minutes=int(options['PAID_ON_BOOT_MINUTES']),
            payment_chunk_minutes=int(options['MINIMUM_PAYMENT_CHUNK_MINUTES']),  # noqa
            shutdown_safety_margin=int(options['SHUTDOWN_SAFETY_MARGIN_MINUTES']),  # noqa
        ):
            logger.critical("Money-saving idle period reached. Shutting down.")
            trigger_shutdown()
        else:
            logger.info("Shutdown does not save money")


def entry_point():
    logging.basicConfig()
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    logger.parent = None

    options = {}
    for name, default in DEFAULTS.items():
        options[name] = os.environ.get(name, default)

    main(options)


if __name__ == '__main__':
    entry_point()
