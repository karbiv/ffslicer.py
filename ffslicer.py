#!/usr/bin/env python3

# copyright Alexander Karbivnichiy
# python 3.4

import os
import sys
from datetime import timedelta
import subprocess
import argparse
from pathlib import PurePath

help_epilog = """It may make sense to keep the list of arguments in a file rather than
typing it out at the command line.

python3 ./ffslicer.py -i input.mp4 @args.txt output.mkv

Each option name in args.txt must be on a separate line, e.g.:
--slices
5.325 7.34 8.325 9.34
15.23 18.49
-preset
superfast
-qp
4
"""

def output_filename_or_exit(kargs, args):
    """Try arguments for 0.1 seconds, and check for errors."""
    args = ['ffmpeg', '-v', 'error', '-i', kargs.input, '-t', '0.1', '-y', '-hide_banner'] + args
    cproc = subprocess.run(args)
    if cproc.returncode != 0: exit(cproc.returncode)
    else:
        try: os.remove(args[-1]) # remove output file
        except FileNotFoundError: pass
            

def delta(ff_time):
    parts = ff_time.split(":")

    hours, minutes = 0, 0
    if len(parts) == 1: # only seconds
        seconds = parts[0]
    elif len(parts) == 2: # minutes and seconds
        seconds = parts[1]
        minutes = int(parts[0])
    else: # hours, minutes, seconds
        seconds = parts[2]
        minutes = int(parts[1])
        hours = int(parts[0])

    sec_parts = seconds.split('.')
    millis = 0
    if len(sec_parts) == 1:
        seconds = int(sec_parts[0])
    elif len(sec_parts) == 2:
        seconds = int(sec_parts[0])
        millis = int("{:0<3.3}".format(sec_parts[1]))
        
    return timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=millis)


def format_delta(td):
    mm, ss = divmod(td.seconds, 60)
    hh, mm = divmod(mm, 60)
    s = "{:0>2d}:{:0>2d}:{:0>2d}".format(hh, mm, ss)
    if td.microseconds: s += '.{:0>6}'.format(td.microseconds)[:4]
    return s


def add_arguments(parser):
    parser.add_argument('-sls', '--slices', dest='slices', nargs='+', required=True, metavar='START STOP',
                        help="Start and stop times(FFMPEG format) for video exerpts to be created.")
    parser.add_argument('-mp', '--multiprocess', dest='multiprocess', action='store_true',
                        help="Multiprocessing. Use separate parallel subprocess for each slice.")
    # -ss option is ignored, slices are converted to -ss/-t options.
    parser.add_argument('-ss', help=argparse.SUPPRESS)
    parser.add_argument('-i', dest="input", help=argparse.SUPPRESS)


def get_slice_name(prefix, start, to, suffix):
    start = start.replace(':', '-')
    to = to.replace(':', '-')
    return prefix + start + '__' + to + suffix


if __name__ == "__main__":

    parser = argparse.ArgumentParser(epilog=help_epilog, fromfile_prefix_chars="@",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(parser)
    
    if len(sys.argv) == 1: parser.print_help(); parser.exit(0)

    args = parser.parse_known_args()
    kargs = args[0] # known arguments, argparse.Namespace object
    args = [arg for arg in args[1] if arg != ''] # all other arguments
    name = sys.argv[0]
    
    times = []
    for el in kargs.slices: times.extend(el.split())
        
    if len(times) % 2 != 0:
        parser.exit(1, "Mistake. Odd number of params to -slice. It must be pairs(START TIME and STOP TIME)")

    pairs = list(zip(times[0::2], times[1::2]))
    output_filename_or_exit(kargs, args) # validate arguments
    output_name = args[-1]
    output_path = PurePath(output_name)
    destdir = output_path.parent
    container = 'ffslices_' + PurePath(kargs.input).name
    try: os.mkdir(str(destdir.joinpath(container)))
    except FileExistsError: pass

    args = args[:-1]
    tasks = []
    cnt = 1
    for start, to in pairs:
        dstart = delta(start)
        duration = delta(to) - dstart
        slice_name = str(destdir.joinpath(
            container,
            get_slice_name(str(cnt) + ') ', start, to, output_path.suffix)))

        tasks.append(['ffmpeg', '-ss', format_delta(dstart), '-i', kargs.input, '-hide_banner'] + \
                     ['-t', format_delta(duration), '-loglevel', 'error', '-stats'] + args + \
                     ['-y', slice_name])
        cnt += 1

    if not kargs.multiprocess:
        print("Starting...")
        for task in tasks:
            print("\nOutput path '{}':".format(task[-1]))
            subprocess.run(task)
        print()
    else:
        from threading  import Thread
        from queue import Queue, Empty
        from collections import namedtuple
        import time
        from curses import wrapper
        import curses

        # FFMPEG sends all the "console output" to stderr because
        # its actual output (the media stream) can go to stdout

        PIPE = subprocess.PIPE
        procs = [subprocess.Popen(task, stdin=PIPE, # important, doesn't break terminal
                                  stderr=PIPE, bufsize=0) for task in tasks]
        
        ffline = namedtuple('ffline', 'queue index')
        qbuf = bytearray(1023)
        
        def enqueue_output(out, ffidx):
            queue = ffidx.queue
            idx = ffidx.index
            cnt = 0
            cr = ord('\r')
            for byte in iter(lambda: out.read(1), b'\n'):
                if len(byte) > 0 and byte[0] != cr:
                    qbuf[cnt] = byte[0]
                    cnt += 1
                elif len(byte) > 0:
                    queue.put(qbuf[:cnt].decode())
                    cnt = 0
            ffprint(idx, qbuf[:cnt].decode())
            out.close()

        def print_queue(ffidx):
            queue = ffidx.queue
            idx = ffidx.index
            while True:
                try: line = queue.get_nowait()
                except Empty: pass 
                else:
                    ffprint(idx, line)
                time.sleep(0.1)

        def ffprint(y, s):
            pad.addstr(y*3, 0, s)
            pad.refresh(0, 0, 0, 0, pad_h-1, pad_w)

        interrupted = False
        try:
            stdscr = curses.initscr()
            curses.curs_set(0)
            pad_h, pad_w = stdscr.getmaxyx()
            pad = curses.newpad(pad_h, pad_w)
            pad.addstr(0, 0, "Starting...")

            for i, proc in enumerate(procs):
                idx = i + 1
                pad.addstr(idx*3-1, 0, "Output path '{}':".format(tasks[i][-1]))
                ffidx = ffline(Queue(), idx)
                ethread = Thread(target=enqueue_output, args=(proc.stderr, ffidx), daemon=True)
                pthread = Thread(target=print_queue, args=(ffidx,), daemon=True)
                ethread.start()
                pthread.start()

            exit_codes = [p.wait() for p in procs]

        except KeyboardInterrupt:
            interrupted = True
        
        finally:
            pad_lines = []
            for i in range(0, pad_h):
                line = pad.instr(i, 0).decode().strip()
                if line: pad_lines.append(line)
            curses.endwin()
            for line in pad_lines: print(line)
            if interrupted: print("\nKeyboard interrupt.")
        
