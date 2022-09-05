# Ramanujan Database
This project is an extension of the [ramanujan project](https://github.com/ShaharGottlieb/MasseyRamanujan).
The project mainly focuses on inserting all of the results that the algorithm find into a database for easier analysis and a centralized source of data.

## Steps for running the service

### Minimum prerequisites
Make sure that your host has python-3.8.10 or above and pip.

### Step 1 - installing required packages
To install the required packages, first run 'sudo apt-get install libpq-dev' (or equivalent, for instance replace 'apt-get' with 'yum -y' if on amazon linux). Then run 'pip install -r requirements.txt' from the root dir of the project. Note that if you're using a specific version of python, the version postfix of the python command should also be appended to the pip command (for instance if you're explicitly calling python3.8 then also explicitly call pip3.8).

### Step 2 - Configuration
Open the config.py in the root dir and configure db_configuration:
- host is the ip/hostname of the remote server
- name is the name of the database (generally should be ramanujan)

If you want you can also configure which jobs will run and with what parameters.

### Step 3 - Running
Open a terminal in the root folder and run the command:
`python ramanujan.py start`  
if you want to stop the process (currently only on linux), run:
`python ramanujan.py stop`  
Note that you can also close the process by just closing the main window.

## Running locally
After configuring the database connection in config.py (step 2), you can also run the code locally if you have a list of PCFs.

### Save to file
Save all of the PCFs in a file, with the following formatting:  
a_n polynomial, b_n polyinomial and a new line between each PCF.  
Each polyinomial should be represented using 'l' as the variable.  
**Example**:  
l^3 - 3/2*l^2 + 383/2352*l - 49585/148176 , (-1/4) * (l - 127/84) * (l - 73/84) * (l - 31/84) * (l + 41/84) * (l + 53/84) * (l + 137/84)  
l^3 - 3/2*l^2 + 2483/5808*l - 57785/574992 , (-1/4) * (l - 197/132) * (l - 149/132) * (l - 83/132) * (l + 67/132) * (l + 115/132) * (l + 247/132)  
l^3 - 3/2*l^2 + 1991/1200*l - 52511/54000 , (-1/4) * (l - 77/60) * (l - 47/60) * (l - 41/60) * (l - 17/60) * (l + 79/60) * (l + 103/60)  
l^3 - 3/2*l^2 - 3469/3888*l + 35663/314928 , (-1/4) * (l - 205/108) * (l - 103/108) * (l - 43/108) * (l + 65/108) * (l + 113/108) * (l + 173/108)  

### Run
After you have the file, run the command `python analyze_cfs.py <name_of_file>`.  
All PCFs and their values will be saved to the database in their Integer PCF form. If the precision of the value will be more than 50 the script will try to compare them to known constants.

## Optional - Creating the database
If you want to create the database, configure the connection details in config.py and then, from the root dir, run `python create_db.py`  
This will create the database and initialize the constant table.
*Note* this will also require you to have the psql program in your path.
