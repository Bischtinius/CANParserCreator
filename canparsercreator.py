#Program takes 6 parameters, 
#package name = Name of the package will be created in the given WS path
#dbc path = path for dbc file containing .dbc file
#package path = Path for WS/src
#package message name = Message file name will be created in the package
#subscribing topic name = Topic for can data
#publisher topic name = Topic name to publish our message
#Usage: python3 canparsercreator.py <package name> <dbc path> <package path> <package message name>(Optional) <subscribing topic name for can messages> <publisher topic name>

from curses.ascii import isupper
import re
import sys
import os
import subprocess
import json

class SignalGroupStruct:
    signals = []
    def __init__(self,name,id,header):
        self.name = name
        self.frameId = id
        self.header = header
        
    def printSGC(self):
        print(self.name,self.frameId)
        print("Signals: ")
        for s in self.signals:
            print(s)   
    
#Reads the header file into a SignalGroupStruct list and returns the list.
def readHeaderFile(filename,db_name):
    frameIds = []
    signals = []
    signalGroups = []
    
    with open(filename) as file:
        for line in file:
            if '/* Frame ids. */' in line:
                break    
        for line_1 in file:
            if '/* Frame lengths in bytes. */' in line_1:
                break 
            frameIds.append(line_1.rstrip('\n'))
        
        frameIds.pop()
        for f in frameIds:
            signalGroups.append(SignalGroupStruct(f.split()[1].lower().replace("frame_id", "t"), f.split()[2].replace("(","").replace(")",""),f.split()[1]))
            
        for counter in range(len(signalGroups)):
            
            for line_2 in file:
                if 'struct' in line_2:
                    break
                
            for line_3 in file:
                if '};' in line_3:
                    break
                
                if 'int' in line_3:
                    signals.append(line_3.strip().split()[1].replace(";",""))
                    
            signalGroups[counter].signals = signals
            signals = []    

    filterList = []

    with open('signal_filter.json') as file:
        filterList = json.load(file)['signals']
    filterList = [db_name + '_' + element.lower() + '_t' for element in filterList]

    if len(filterList) > 0:
        signalGroups = [signal for signal in signalGroups if signal.name in filterList]  

    return signalGroups   

#Converts signal names in the DBC to names in the header file
def DbcNametoHeadName(sigNames):
    convertedNames = []
    for name in sigNames:
        prev = 'k'
        for index in range(0,len(name)):
            if isupper(name[0]):
                name = name[:index] + name[index].lower() + name[index+1:]
                prev = 'b' 
                
            if not index == 0:
                if isupper(name[index]) and prev == 'k':
                    name = name[:index] + name[index].lower() + name[index+1:]
                    name = name[:index] + "_" + name[index:]
                    prev = 'b'
                
                elif isupper(name[index]) and (prev == 'b' or prev == '_'):
                    name = name[:index] + name[index].lower() + name[index+1:]
                    prev = 'b'
                    
                elif name[index] == '_':
                    prev = '_'
                    
                else:
                    prev = 'k'        
                         
        convertedNames.append(name)
                       
    return convertedNames

def bitDetermine(range):
    min = range.replace('[','').replace(']','').split('|')[0]
    minFloat = float(min)
    max = range.replace('[','').replace(']','').split('|')[1]
    maxFloat = float(max)
    total = float()
    if minFloat < 0 and maxFloat > 0:
        total = maxFloat - minFloat
        
    elif minFloat < 0 and maxFloat < 0:
        total = -maxFloat - minFloat     
    
    else:
        total = maxFloat + minFloat
        
    if total < 256:
        return 8
    
    elif total < 65536:
        return 16
    
    elif total < 4294967296:
        return 32    
    
    else:
        return 64

#Converts the dbc encoding to utf-8 and determines the types in the message according to dbc and writes to the message file.                                 
def fillMessage(structs,msg_path,dbc_path):

    cmd = ['chardet3', dbc_path]
    charenc = subprocess.Popen(cmd, stdout=subprocess.PIPE ).communicate()[0].split()[1].decode("utf-8")
    print('\nDetected encoding format of the DBC is ' + charenc +'\n')
    try:
        os.system('iconv -f '+charenc+' -t utf-8 ' + dbc_path + " > " + dbc_path+".txt")
        
    except:
        print('DBC could not opened with detected encoding format!')    
        
    regexPattern = '(\[.+\|.+\])'
    vals = []
    signalName = []
    signalId = []
    with open(dbc_path+".txt") as dbc:
        for line in dbc:
            if 'VAL_ ' in line:
                vals.append(line.split()[2])
                
            if re.search(regexPattern,line.rstrip('\n')):
                signalName.append(line.rstrip('\n').split()[1])
                signalId.append(line.rstrip('\n').split()[5])
                    
    signalName = DbcNametoHeadName(signalName)
    vals = DbcNametoHeadName(vals)     
                               
    for struct in structs:
        with open(msg_path+struct.name+'.msg', 'w') as mf:
            mf.write("std_msgs/Header header\n")
            mf.write("\n")
            mf.write("# %s "% struct.name.upper())
            mf.write("%s\n" % struct.frameId)
            for signal in struct.signals:
                if (signal in vals):
                    mf.write("uint")
                    try:
                        mf.write("%d " %bitDetermine(signalId[signalName.index(signal)]))
                    except:
                        print("Signal "+signal+" did not find in the DBC")
                        return -1
                    
                    mf.write('_'.join(struct.name.split('_')[1:len(struct.name.split('_'))-1]))        
                    mf.write("_%s\n" %signal)
                else:
                    mf.write("float")
                    try:
                        bit = bitDetermine(signalId[signalName.index(signal)])
                    except:
                        print("Signal "+signal+" did not find in the DBC")
                        return -1
                    
                    if bit < 32:
                        bit = 32
                    mf.write("%d " %bit)
                    mf.write('_'.join(struct.name.split('_')[1:len(struct.name.split('_'))-1])) 
                    mf.write("_%s\n" %signal)
                    
            mf.write("\n")
    os.system("rm -rf " +dbc_path+".txt")                

#Writes ROS node                                    
def writeCpp(structs,srcPath,dbName,sbsTopic):
    
    headers = '#include <ros/ros.h>\n#include "can_msgs/Frame.h"\n#include "'+dbName+'.h"\n'
    headers_msg = ""
    for struct in structs:
        headers_msg += '#include "'+dbName+'/'+struct.name+'.h"\n'
    namespace = 'using namespace std;'
              
    classPublic = 'class '+dbName.upper()+'Feedback{\n\tpublic:\n\t\t'+dbName.upper()+\
    'Feedback(){\n\t\t\tros::NodeHandle private_nh;\n\t\t\tcan_sub = private_nh.subscribe("'+sbsTopic+'", 1000, &'+dbName.upper()+\
    'Feedback::canCallback, this);\n'
    for struct in structs:
        classPublic += '\t\t\t'+struct.name+'_pub = private_nh.advertise<'+dbName+'::'+struct.name+'>("'+struct.name+'", 1);\n'
    classPublic += '\t\t}\n\t\t~'+dbName.upper()+'Feedback(){}'

    classPrivate = '\n\tprivate:\n'
    for struct in structs:
        classPrivate += '\t\tros::Publisher '+struct.name+'_pub;\n'
    classPrivate += '\t\tros::Subscriber can_sub;\n'
    
    for struct in structs:
        pName = '_'.join(struct.name.split('_')[1:len(struct.name.split('_'))-1])
        classPrivate += '\t\t'+struct.name+' *'+pName+' = new '+struct.name+';\n' 

    callBack = '\n\t\tvoid canCallback(const can_msgs::Frame msg){\n'
    callBack += '\t\t\tuint id = (msg.id > 2147483647) ? msg.id ^ 0x80000000 : msg.id;\n'
    
    for struct in structs:
        callBack += '\t\t\t'+dbName+'::'+struct.name.lower()+' '+struct.name.lower()+'_msg;\n'

    callBack += '\n\t\t\tswitch(id){'
    
    for struct in structs:
        pName = '_'.join(struct.name.split('_')[1:len(struct.name.split('_'))-1])
        callBack += '\n\t\t\t\tcase ' +struct.header + ':\n'
        callBack += '\t\t\t\t\t'+struct.header.lower().replace("_frame_id","_unpack")+'('+ pName + ',msg.data.data(),8);\n'
        for signal in struct.signals:
            callBack += '\t\t\t\t\t'+struct.name.lower()+'_msg.'+'_'.join(struct.name.split('_')[1:len(struct.name.split('_'))-1])+'_'+signal+' = ' +'_'.join(struct.name.split('_')[0:len(struct.name.split('_'))-1])+\
            '_'+signal+'_decode('+'_'.join(struct.name.split('_')[1:len(struct.name.split('_'))-1])+'->'+signal+');\n'
        callBack += '\t\t\t\t\t'+struct.name.lower()+'_msg.header.stamp = ros::Time::now();\n\t\t\t\t\t'+struct.name.lower()+'_msg.header.seq++;\n'
        callBack += '\t\t\t\t\t'+struct.name+'_pub.publish('+struct.name.lower()+'_msg);\n'
        callBack += '\t\t\t\t\tbreak;\n' 

    default_case = '\n\t\t\t\tdefault:\n\t\t\t\t\tROS_WARN(\"Unkown CAN_FRAME_ID\");\n\t\t\t\t\tbreak;\n\t\t\t\t}\n\t}\n};\n'
    
    intMain = '\nint main(int argc, char *argv[])\n{\n\tros::init(argc,argv,"'+dbName+'_feedback");\n\t'+dbName.upper()+'Feedback '+dbName+\
    ';\n\tros::spin();\n\treturn 0;\n}'

    with open(srcPath, 'w') as cpp:
        cpp.write(headers+'\n')
        cpp.write(headers_msg+'\n')
        cpp.write(namespace+'\n\n')
        cpp.write(classPublic+'\n')
        cpp.write(classPrivate)
        cpp.write(callBack)
        cpp.write(default_case)
        cpp.write(intMain)

def update_CMakeLists(structs,srcPath):
    lines = []
    with open(srcPath+'/CMakeLists.txt', 'r') as file:
        lines = file.readlines()

        for struct in structs:
            lines.insert(18,'   '+struct.name+'.msg\n')

    with open(srcPath+'/CMakeLists.txt', 'w') as file:
        file.writelines(lines)

def main():        
    if len(sys.argv) == 5:
        db_name = sys.argv[1]
        dbc_path = sys.argv[2]
        pckg_path = sys.argv[3]
        sbs_topic = sys.argv[4]
        
    else:
        print("Invalid Arguments!")
        print("Usage: python3 canparsercreator.py <package name> <dbc path> <package path> <subscribing topic name for can messages>")
        return -1
    
    files = os.listdir('.')
    if not 'env' in files:
        os.system("chmod +x scripts/install.sh")
        os.system("scripts/install.sh")
    
    os.system("chmod +x scripts/generateParser.sh")       
    os.system("scripts/generateParser.sh " + db_name + " " + dbc_path + " " + pckg_path + " " + sbs_topic)
    structs = readHeaderFile(pckg_path+'/'+db_name+'/include/'+db_name+'.h',db_name)
    fillMessage(structs,pckg_path+'/'+db_name+'/msg/',dbc_path)
    update_CMakeLists(structs,pckg_path+'/'+db_name)
    writeCpp(structs,pckg_path+'/'+db_name+'/src/'+db_name+'_parser.cpp',db_name,sbs_topic)
    stringMsg = 'Can parser [' +db_name+ '] was created SUCCESSFULLY!'
    print(stringMsg)
                                                            
if __name__ == '__main__':
    exit(main())