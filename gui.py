from tkinter import *
import os
import re
import subprocess
from sys import platform

# version number
version = "v0.0.2"

class IOCAction:


    """
    Helper class that stores information and functions for each IOC in the CONFIGURE file

    Attributes
    ----------
    ioc_type : str
        name of areaDetector driver instance the IOC is linked to ex. ADProsilica
    ioc_name : str
        name of the IOC ex. cam-ps1
    ioc_port : str
        telnet port on which procserver will run the IOC
    connection : str
        Value used to connect to the device ex. IP, serial num. etc.
    ioc_num : int
        Counter that keeps track of which IOC it is

    Methods
    -------
    process(ioc_top : str, bin_loc : str, bin_flat : bool)
        clones ioc-template instance, sets up appropriate st.cmd.
    update_unique(ioc_top : str, bin_loc : str, bin_flat : bool, prefix : str, engineer : str, hostname : str, ca_ip : str)
        Updates unique.cmd file with all of the required configuration options
    update_config(ioc_top : str, hostname : str)
        updates the config file with appropriate options
    fix_env_paths(ioc_top: str, bin_flat : bool)
        fixes the existing envpaths with new locations
    getIOCbin(bin_loc : str, bin_flat : bool)
        finds the path to the binary for the IOC based on binary top location
    cleanup(ioc_top : str)
        runs cleanup.sh script to remove unwanted files in generated IOC.
    """

    def __init__(self, ioc_type, ioc_name, ioc_port, connection, ioc_num):
        """
        Constructor for the IOCAction class

        Parameters
        ----------
        ioc_type : str
        name of areaDetector driver instance the IOC is linked to ex. ADProsilica
        ioc_name : str
            name of the IOC ex. cam-ps1
        ioc_port : str
            telnet port on which procserver will run the IOC
        connection : str
            Value used to connect to the device ex. IP, serial num. etc.
        ioc_num : int
            Counter that keeps track of which IOC it is
        """

        self.ioc_type = ioc_type
        self.ioc_name = ioc_name
        self.ioc_port = ioc_port
        self.connection = connection
        self.ioc_num = ioc_num
    

    def process(self, ioc_top, bin_loc, bin_flat):
        """
        Function that clones ioc-template, and pulls correct st.cmd from startupScripts folder
        The binary for the IOC is also identified and inserted into st.cmd

        Parameters
        ----------
        ioc_top : str
            Path to the top directory to contain generated IOCs
        bin_loc : str
            path to top level of binary distribution
        bin_flat : bool
            flag for deciding if binaries are flat or stacked

        Returns
        -------
        int
            -1 if error, 0 if success
        """

        print("-------------------------------------------")
        print("Setup process for IOC " + self.ioc_name)
        print("-------------------------------------------")
        out = subprocess.call(["git", "clone", "--quiet", "https://github.com/epicsNSLS2-deploy/ioc-template", ioc_top + "/" + self.ioc_name])
        if out != 0:
            print("Error failed to clone IOC template for ioc {}".format(self.ioc_name))
            return -1
        else:
            print("IOC template cloned, converting st.cmd")
            ioc_path = ioc_top +"/" + self.ioc_name
            os.remove(ioc_path+"/st.cmd")

            startup_path = ioc_path+"/startupScripts"
            startup_type = self.ioc_type[2:].lower()

            found = False

            for file in os.listdir(ioc_path +"/startupScripts"):
                if startup_type in file.lower():
                    startup_path = startup_path + "/" + file
                    found = True
                    break
            if not found:
                print('ERROR - {} is not yet supported by initIOCs, skipping'.format(self.ioc_type))
                return -1
            
            example_st = open(startup_path, "r+")
            st = open(ioc_path+"/st.cmd", "w+")

            line = example_st.readline()

            while line:
                if "#!" in line:
                    st.write("#!" + self.getIOCBin(bin_loc, bin_flat) + "\n")
                elif "envPaths" in line:
                    st.write("< envPaths\n")
                else:
                    st.write(line)

                line = example_st.readline()

            example_st.close()
            st.close()

            autosave_path = ioc_path + "/autosaveFiles"
            autosave_type = self.ioc_type[2:].lower()
            if os.path.exists(autosave_path + "/" + autosave_type + "_auto_settings.req"):
                print("Generating auto_settings.req file for IOC {}.".format(self.ioc_name))
                os.rename(autosave_path + "/" + autosave_type + "_auto_settings.req", ioc_path + "/auto_settings.req")
            else:
                print("Could not find supported auto_settings.req file for IOC {}.".format(self.ioc_name))

            if os.path.exists(ioc_path + "/dependancyFiles"):
                for file in os.listdir(ioc_path + "/dependancyFiles"):
                    if startup_type in file.lower():
                        print('Copying dependency file {} for {}'.format(file, self.ioc_type))
                        os.rename(ioc_path + "/dependancyFiles/" + file, ioc_path + "/" + file)

            return 0


    def update_unique(self, ioc_top, bin_loc, bin_flat, prefix, engineer, hostname, ca_ip):
        """
        Function that updates the unique.cmd file with all of the required configurations

        Parameters
        ----------
        ioc_top : str
            Path to the top directory to contain generated IOCs
        bin_loc : str
            path to top level of binary distribution
        bin_flat : bool
            flag for deciding if binaries are flat or stacked
        prefix : str
            Prefix given to the IOC
        engineer : str
            Name of the engineer deploying the IOC
        hostname : str
            name of the host IOC server on which the IOC will run
        ca_ip : str
            Channel Access IP address
        """

        if os.path.exists(ioc_top + "/" + self.ioc_name +"/unique.cmd"):
            print("Updating unique file based on configuration")
            unique_path = ioc_top + "/" + self.ioc_name +"/unique.cmd"
            unique_old_path = ioc_top +"/" + self.ioc_name +"/unique_OLD.cmd"
            os.rename(unique_path, unique_old_path)

            uq_old = open(unique_old_path, "r")
            uq = open(unique_path, "w")
            line = uq_old.readline()
            while line:
                if not line.startswith('#'):
                    if "SUPPORT_DIR" in line:
                        if bin_flat:
                            uq.write('epicsEnvSet("SUPPORT_DIR", "{}")\n'.format(bin_loc))
                        else:
                            uq.write('epicsEnvSet("SUPPORT_DIR", "{}")\n'.format(bin_loc + "/support"))
                    elif "ENGINEER" in line:
                        uq.write('epicsEnvSet("ENGINEER", "{}")\n'.format(engineer))
                    elif "CAM-CONNECT" in line:
                        uq.write('epicsEnvSet("CAM-CONNECT", "{}")\n'.format(self.connection))
                    elif "HOSTNAME" in line:
                        uq.write('epicsEnvSet("HOSTNAME", "{}")\n'.format(hostname))
                    elif "PREFIX" in line and "CTPREFIX" not in line:
                        uq.write('epicsEnvSet("PREFIX", "{}")\n'.format(prefix + "{{{}}}".format(self.ioc_type[2:] +"-Cam:{}".format(self.ioc_num))))
                    elif "CTPREFIX" in line:
                        uq.write('epicsEnvSet("CTPREFIX", "{}")\n'.format(prefix + "{{{}}}".format(self.ioc_type[2:] +"-Cam:{}".format(self.ioc_num))))
                    elif "IOCNAME" in line:
                        uq.write('epicsEnvSet("IOCNAME", "{}")\n'.format(self.ioc_name))
                    elif "EPICS_CA_ADDR_LIST" in line:
                        uq.write('epicsEnvSet("EPICS_CA_ADDR_LIST", "{}")\n'.format(ca_ip))
                    elif "IOC" in line and "IOCNAME" not in line:
                        uq.write('epicsEnvSet("IOC", "{}")\n'.format("ioc"+self.ioc_type))
                    elif "PORT" in line:
                        uq.write('epicsEnvSet("PORT", "{}")\n'.format(self.ioc_type[2:]+"1"))
                    else:
                        uq.write(line)
                else:
                    uq.write(line)
                line = uq_old.readline()

            uq_old.close()
            uq.close()
        else:
            print("No unique file found, proceeding to next step")


    def update_config(self, ioc_top, hostname):
        """
        Function that updates the config file with the correct IOC name, port, and hostname

        Parameters
        ----------
        ioc_top : str
            Path to the top directory to contain generated IOCs
        hostname : str
            name of the host IOC server on which the IOC will run
        """

        conf_path = ioc_top + "/" + self.ioc_name + "/config"
        if os.path.exists(conf_path):
            print("Updating config file for procServer connection")
            conf_old_path = ioc_top + "/" + self.ioc_name + "/config_OLD"
            os.rename(conf_path, conf_old_path)
            cn_old = open(conf_old_path, "r")
            cn = open(conf_path, "w")
            line = cn_old.readline()
            while line:
                if "NAME" in line:
                    cn.write("NAME={}\n".format(self.ioc_name))
                elif "PORT" in line:
                    cn.write("PORT={}\n".format(self.ioc_port))
                elif "HOST" in line:
                    cn.write("HOST={}\n".format(hostname))
                else:
                    cn.write(line)
                line = cn_old.readline()
            cn_old.close()
            cn.close()
        else:
            print("No config file found moving to next step")


    def fix_env_paths(self, ioc_top, bin_flat):
        """
        Function that fixes the envPaths file if binaries are not flat

        Parameters
        ----------
        ioc_top : str
            Path to the top directory to contain generated IOCs
        bin_flat : bool
            flag for deciding if binaries are flat or stacked
        """

        env_path = ioc_top + "/" + self.ioc_name + "/envPaths"
        if os.path.exists(env_path):
            env_old_path = ioc_top + "/" + self.ioc_name + "/envPaths_OLD"
            os.rename(env_path, env_old_path)
            env_old = open(env_old_path, "r")
            env = open(env_path, "w")
            line = env_old.readline()
            while line:
                if "EPICS_BASE" in line and not bin_flat:
                    print("Fixing base location in envPaths")
                    env.write('epicsEnvSet("EPICS_BASE", "$(SUPPORT)/../base")\n')
                else:
                    env.write(line)
                line = env_old.readline()
            env_old.close()
            env.close()


    def getIOCBin(self, bin_loc, bin_flat):
        """
        Function that identifies the IOC binary location based on its type and the binary structure

        Parameters
        ----------
        bin_loc : str
            path to top level of binary distribution
        bin_flat : bool
            flag for deciding if binaries are flat or stacked
        
        Return
        ------
        driver_path : str
            Path to the IOC executable located in driverName/iocs/IOC/bin/OS/driverApp
        """

        if bin_flat:
            # if flat, there is no support directory
            driver_path = bin_loc + "/areaDetector/" + self.ioc_type
        else:
            driver_path = bin_loc + "/support/areaDetector/" + self.ioc_type
        # identify the IOCs folder
        for name in os.listdir(driver_path):
            if "ioc" == name or "iocs" == name:
                driver_path = driver_path + "/" + name
                break
        # identify the IOC 
        for name in os.listdir(driver_path):
            if "IOC" in name or "ioc" in name:
                driver_path = driver_path + "/" + name
                break 
        # Find the bin folder
        driver_path = driver_path + "/bin"
        # There should only be one architecture
        for name in os.listdir(driver_path):
            driver_path = driver_path + "/" + name
            break
        # We look for the executable that ends with App
        for name in os.listdir(driver_path):
            if 'App' in name:
                driver_path = driver_path + "/" + name
                break

        return driver_path


    def cleanup(self, ioc_top):
        """ Function that runs the cleanup.sh/cleanup.bat script in ioc-template to remove unwanted files """

        cleanup_completed = False

        if platform == "linux":
            if(os.path.exists(ioc_top + "/" + self.ioc_name + "/cleanup.sh")):
                print("Performing cleanup for {}".format(self.ioc_name))
                out = subprocess.call(["bash", ioc_top + "/" + self.ioc_name + "/cleanup.sh"])
                print()
                cleanup_completed = True
        elif platform == "win32":
            if(os.path.exists(ioc_top + "/" + self.ioc_name + "/cleanup.bat")):
                print("Performing cleanup for {}".format(self.ioc_name))
                out = subprocess.call([ioc_top + "/" + self.ioc_name + "/cleanup.bat"])
                print()
                cleanup_completed = True
        if os.path.exists(ioc_top +"/" + self.ioc_name + "/st.cmd"):
            os.chmod(ioc_top +"/" + self.ioc_name + "/st.cmd", 0o755)
        if not cleanup_completed:
            print("No cleanup script found, using outdated version of IOC template")


#-------------------------------------------------
#----------------MAIN SCRIPT FUNCTIONS------------
#-------------------------------------------------


def read_ioc_config():
    """
    Function for reading the CONFIGURE file. Returns a dictionary of configure options,
    a list of IOCAction instances, and a boolean representing if binaries are flat or not

    Returns
    -------
    ioc_actions : List of IOCAction
        list of IOC actions that need to be performed.
    configuration : dict of str -> str
        Dictionary containing all options read from configure
    bin_flat : bool
        toggle for flat or stacked binary directory structure
    """

    ioc_config_file = open("CONFIGURE.txt", "r+")
    ioc_actions = []
    configuration = {}
    bin_flat = True
    ioc_num_counter = 1

    line = ioc_config_file.readline()
    while line:
        if "=" in line and not line.startswith('#') and "BINARIES_FLAT" not in line:
            line = line.strip()
            split = line.split('=')
            configuration[split[0]] = split[1]
        elif "BINARIES_FLAT" in line:
            if "NO" in line:
                bin_flat = False
        elif not line.startswith('#') and len(line) > 1:
            line = line.strip()
            line = re.sub(' +', ' ', line)
            temp = line.split(' ')
            ioc_action = IOCAction(temp[0], temp[1], temp[2], temp[3], ioc_num_counter)
            ioc_num_counter = ioc_num_counter + 1
            ioc_actions.append(ioc_action)

        line = ioc_config_file.readline()

    ioc_config_file.close()
    return ioc_actions, configuration, bin_flat


def init_ioc_dir(ioc_top):
    """
    Function that creates ioc directory if it has not already been created.

    Parameters
    ----------
    ioc_top : str
        Path to the top directory to contain generated IOCs
    """

    if ioc_top == "":
        print("Error: IOC top not initialized")
        exit()
    elif os.path.exists(ioc_top) and os.path.isdir(ioc_top):
        print("IOC Dir already exits.")
        print()
    else:
        os.mkdir(ioc_top)


def print_start_message():
    """
    Function for printing initial message
    """

    print("+----------------------------------------------------------------+")
    print("+ initIOCs, Version: " + version +"                                      +")
    print("+ Author: Jakub Wlodek                                           +")
    print("+ Copyright (c): Brookhaven National Laboratory 2018-2019        +")
    print("+ This software comes with NO warranty!                          +")
    print("+----------------------------------------------------------------+")
    print()


def init_iocs():
    """
    Main driver function. First calls read_ioc_config, then for each instance of IOCAction
    perform the process, update_unique, update_config, fix_env_paths, and cleanup functions
    """

    print_start_message()
    actions, configuration, bin_flat = read_ioc_config()
    init_ioc_dir(configuration["IOC_DIR"])
    for action in actions:
        out = action.process(configuration["IOC_DIR"], configuration["TOP_BINARY_DIR"], bin_flat)
        if out == 0:
            action.update_unique(configuration["IOC_DIR"], configuration["TOP_BINARY_DIR"], bin_flat, 
                configuration["PREFIX"], configuration["ENGINEER"], configuration["HOSTNAME"], 
                configuration["CA_ADDRESS"])
            action.update_config(configuration["IOC_DIR"], configuration["HOSTNAME"])
            action.fix_env_paths(configuration["IOC_DIR"], bin_flat)
            action.cleanup(configuration["IOC_DIR"])










class Window(Frame):



# Define settings upon initialization. Here you can specify
    def __init__(self, master=None):     
        # parameters that you want to send through the Frame class. 
        Frame.__init__(self, master)   

        #reference to the master widget, which is the tk window                 
        self.master = master

        #with that, we want to then run init_window, which doesn't yet exist
        self.init_window()
    

    #Creation of init_window
    def init_window(self):
        
        v1 = StringVar()
        v2 = StringVar()
        v3 = StringVar()
        v4 = StringVar()
        v5 = StringVar()

        # changing the title of our master widget      
        self.master.title("initIOC_GUI")

        w = Label(root, text="ioc_type").place(x=30,y=50)

        e1 = Entry(root, textvariable=v1).place(x=80,y=50)

        w = Label(root, text = "")

        w = Label(root, text="ioc_name").place(x=30, y=70)
        
        e2 = Entry(root,textvariable=v2).place(x=85, y=70)
        
        w = Label(root, text = "")

        w = Label(root, text="ioc_port").place(x=30,y=100)

        e3 = Entry(root,textvariable=v3).place(x=85, y=100)

        w = Label(root, text = "")

        w = Label(root, text="connection").place(x=30,y=130)

        e4 = Entry(root,textvariable=v4).place(x=95,y=130)

        w = Label(root, text = "")


        w = Label(root, text="ioc_num").place(x=30,y=160)

        e5 = Entry(root,textvariable=v5).place(x=85,y=160)

        w = Label(root, text = "")

        # allowing the widget to take the full space of the root window
        self.pack(fill=BOTH, expand=1)

        # creating a button instance
        quitButton = Button(self, text="Exit",command=self.client_exit)

        addButton = Button(self, text ="Add", command=lambda: self.add_ioc(v1,v2,v3,v4,v5))

        advanceButton = Button(self, text = "Advance", command=self.advance_option)



        # placing the button on my window
        quitButton.place(x=0, y=0)

        addButton.place(x=100,y=1)

        advanceButton.place(x=200, y =2)

        

    def client_exit(self):
        exit()

    def add_ioc(self, v1,v2,v3,v4,v5):
        print("Hello, thanks for adding")
        print("Inside v1 is: "+v1.get())
        print("Inside v2 is: "+v2.get())
        print("Inside v3 is: "+v3.get())
        print("Inside v4 is: "+v4.get())
        print("Inside v5 is: "+v5.get())

        
        location = 0
        i = 0
        arr = []
        with open("CONFIGURE.txt","r+") as fo:
            print("I opened")
            for line in fo:
                line = line.strip()
                arr.append(line+"\n")
                if line.startswith("#-------------------------------------------------------------------------"):
                    location = i
                    print(location)
                    print("*******************************")
                    arr.append("\n")
                    camera_info = "          " + v1.get() + "   " + v2.get() + "         " + v3.get() + "         " + v4.get() + "         " + v5.get()
                    arr.append(camera_info+ "\n")
                    
            i = i + 1
            fo.seek(0)
            fo.truncate()
            fo.writelines(arr)
        fo.close()
        init_iocs()
            
        
        


    def advance_option(self):
        w = Label(root, text="ioc_dir").place(x=30,y=190)


        e6 = Entry(root).place(x=85,y=190)


        w = Label(root, text = "")


        w = Label(root, text="top_binary_dir").place(x=30,y=210)

        
        e7 = Entry(root).place(x=115,y=210)

        
        w = Label(root, text = "")


        w = Label(root, text="binaries_flat").place(x=30,y=240)


        e8 = Entry(root).place(x=115,y=240)


        w = Label(root, text = "")


        w = Label(root, text="engineer").place(x=30,y=270)


        e9 = Entry(root).place(x=90,y=270)


        w = Label(root, text = "")


        w = Label(root, text="prefix").place(x=30,y=300)

        e10 = Entry(root).place(x=90,y=300)

        w = Label(root, text = "")

        w = Label(root, text="hostname").place(x=30,y=330)

        e11 = Entry(root).place(x=100,y=330)

        w = Label(root, text = "")

        w = Label(root, text="ca_address").place(x=30,y=360)
        
        e12 = Entry(root).place(x=90,y=360)
        
        w = Label(root, text = "")





root = Tk()

root.geometry("1080x1080")

app = Window(root)
root.mainloop()




