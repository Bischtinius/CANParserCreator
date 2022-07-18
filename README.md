# CANParserCreator for ROS1

## Requeriments

```
    catkin_tools 0.9.0
    python3
```

## About
A tool for parsing CAN DBCs using cantools (https://cantools.readthedocs.io/en/latest/).
Generates a virtual environment and installs cantools and chardet (https://pypi.org/project/chardet/) (To detect encoding format of the dbc file)
After creates a ROS1 package using catkin, script generates a rosnode which subscribes to name given topic and publish the ros message to another name given topic using the header and the source file generated by cantool.

## Usage

Program takes 6 parameters,<br />
package name = Name of the package will be created in the given WS path <br />
dbc path = path for dbc file containing .dbc file <br />
package path = Path for WS/src <br />
package message name (optional) = Message file name will be created in the package <br />
subscribing topic name = Topic for can data <br />
publisher topic name = Topic name to publish our message  <br />   

```
python3 canparsercreator.py <package name> <dbc path> <package path> <package message name> <subscribing topic name for can messages> <publisher topic name>
```