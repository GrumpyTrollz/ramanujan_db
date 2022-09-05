'''how this works:
Every job is run (at most) 'iterations' amount of times, defaults to infinity.
Every name must correspond to a file in jobs folder of the format 'job_*.py'.
In each file, the simpler case is when it doesn't have the function 'run_query',
and then it runs 'execute_job' with 'args' and finishes.
Otherwise it runs 'run_query' with 'args' and then 'execute_job' with its results,
and finally 'summarize_results' with the results of that.
Also, in the latter mode, if 'execute_job' needs access to the configuration,
setting 'EXECUTE_NEEDS_ARGS' to True in the file and specifying
all of the configuration as parameters after 'query_data' does the trick.
'''
configuration = {
    'pool_size': 10,
    'jobs_to_run': {
        'generate_cfs_random': {
            'args': { 'bulk': 5000, 'max_deg': 3, 'max_coeff': 50, 'num_denom_factor': (2, True)  },
            'iterations': 2
        },
        'calculate_precision': {
            'args': { 'bulk': 1000, 'num_denom_factor': (2, True) },
            'run_async': True,
            'async_cores': 4,
            'cooldown': 30,
            'no_work_timeout': 60
        },
        'poly_pslq': {
            'args': { 'bulk': 1000, 'num_denom_factor': (2, True), 'num_of_consts': (2, True), 'num_of_cfs': (1, True), 'degree': (2, 1), 'use_artificial': False },
            'run_async': True,
            'async_cores': 4,
            'cooldown': 30,
            'no_work_timeout': 60
        }
    }
}

# If you make your own database, 'name' must match the name in 'create_db.sql' in the line 'CREATE DATABASE <name>'
db_configuration = {
    'host': '',
    'port': 5432,
    'user': '',
    'passwd': '',
    'name': ''
}

def get_connection_string(db_name=None):
    conf = db_configuration.copy()
    if db_name:
        conf['name'] = db_name
    return 'postgresql://{user}:{passwd}@{host}:{port}/{name}'.format(**conf)
