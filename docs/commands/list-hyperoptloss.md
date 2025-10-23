```
usage: freqtrade list-hyperoptloss [-h] [-v] [--no-color] [--logfile FILE]
                                   [-V] [-c PATH] [-d PATH] [--userdir PATH]
                                   [--hyperopt-path PATH] [-1]

options:
  -h, --help            show this help message and exit
  --hyperopt-path PATH  Specify additional lookup path for Hyperopt Loss
                        functions.
  -1, --one-column      Print output in one column.

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile FILE, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c PATH, --config PATH
                        Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d PATH, --datadir PATH, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir PATH, --user-data-dir PATH
                        Path to userdata directory.

```
