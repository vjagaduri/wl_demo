# * @(#)CdocmWlConfig.py 1.0  21/4/2014
# *
# * Copyright: Copyright 2014 Polaris Software Lab Limited. All rights reserved.
# * Description	: This allows to handle Weblogic resource creation/updation, 
# *  deploy/undeploy, managed server stop/start and managed server startup script 
# *  generation
# * Usage 1: CdocmWlConfig.py <Config XML File> 
# *   - To create or update weblogic resource
# *   - To generate html report for the availability of resource
# * Usage 2: CdocmWlConfig.py <Config XML File> -validate
# *   - To generate html report for the availability of resource
# * Addtional sources	: <path of xml, that needs to be passed as a command line argument>
# * Author		: Satheesh.Iyavoo - CDOO Team
# * History:
# * 21 Apr 14 
# * - Added support to stop/start managed server
# * - Added support to create startup script for managed server
# * 12 May 14
# * - Added feature to generate html report for resource availability
# * Jul 2
# * - Added support for Queue ErrorDestination
# * Aug 26 (Suganya & VTJ)
# * - Added for Cluster CIBC Specific
# * Dec 28 (VTJ)
# * - Added TransactionParams param for CF
# * - Added Queues and Topics apart from UniformDistributedQueue & UniformDistibutedTopic

import traceback, os, sys, commands
# sys.path.insert(0, 'Lib')
from os.path import basename
import re
from xml.dom import minidom
from java.io import *


# Utility function to validate commandline argument
def validateArg():
  if len( sys.argv ) == 2:
    configXmlFile = sys.argv[1]
    # Validate config XML file
    if not os.path.exists( configXmlFile ):
      sys.exit( 'ERROR: Config xml file %s was not found!' % configXmlFile )
  elif len( sys.argv ) == 3:
    print "=== Validating Weblogic Resources ==="
  else:
    print "Usage 1: CdocmWlConfig.py" + " <Config XML File> - To Create/Update weblogic resource"
    print "Usage 2: CdocmWlConfig.py" + " <Config XML File> -validate - To Validate the existence of weblogic resources"
    sys.exit( -1 )

def p( varName, varValue ):
    print "varName: " + str(varValue)
    # frame, filename, lineNumber, functionName, lines, index=\
    #   inspect.getouterframes(inspect.currentframe())[1]
    # print "<" + str(functionName) + ":" + str(lineNumber) \
    #   + ">:" + str(varName) + ":" + str(varValue)

class CdocmWlConfig:
  def __init__( self, configXmlFile ):  
    self.report = {}
    self.configXmlFile = configXmlFile
    self.reportBasename = os.path.splitext(basename(self.configXmlFile))[0]
    self.reportPath = "../Reports"
    
    self.xmldoc = minidom.parse( configXmlFile )
    self.loadSecret()
    self.connectDomain()
    self.createResources()
    #self.validateResources()
    #self.htmlReport()
    #self.jsonReport()

  def loadSecret(self):
    self.secret = {}
    connection = self.xmldoc.getElementsByTagName("connection")
    connectProp = connection[0].getElementsByTagName("prop")

    # Process secret values for <connection>
    self.secret['connection'] = {}
    for prop in connectProp:
      if 'secret' in prop.attributes.keys():
        propName = prop.attributes['name'].value
        propValue = self.getPassword('Secret value for ' + propName + ' :')
        self.secret['connection'][propName] = propValue

    # Process secret values for <res>
    resources = self.xmldoc.getElementsByTagName("res") 
    for resource in resources:  
      name = resource.attributes['name'].value
      type = resource.attributes['type'].value 
      self.secret[name] = {}
      properties = resource.getElementsByTagName("prop") 
      for property in properties:
        if 'secret' in property.attributes.keys():
          propName = property.attributes['name'].value
          propValue = self.getPassword('Secret value for ' + type + ' >> ' + name + ' >> ' + propName + ' :')
          self.secret[name][propName] = propValue


  def connectDomain( self ):
    connection = self.xmldoc.getElementsByTagName("connection")
    connectProp = connection[0].getElementsByTagName("prop")
    user = password = host = port = ''
    for prop in connectProp:
      propName = prop.attributes['name'].value
      if 'value' in prop.attributes.keys():
        propValue = prop.attributes['value'].value
      if 'secret' in prop.attributes.keys():
        propValue = self.secret['connection'][propName]
      if propName == 'admin-user':
        user = propValue
      if propName == 'admin-password':
        password = propValue
      if propName == 'admin-host':
        host = propValue
      if propName == 'admin-port':
        port = propValue
    adminurl = "t3://" + host + ":" + port
    #p( "host", host )
    #p( "port", port )
    #p( "user", user )
    # p( "password", password )
    p( "adminurl", adminurl )    
    try:
      connect(user, password, adminurl)
    except:
      self.catchExcp()

  def wl_update(self):
    edit()
    startEdit()
    
  def wl_activate(self):
    save()
    activate()

  def pathExists(self, path):
    exists = getMBean(path)
    if(exists != None):
      return 1
    else:
      return 0

  def createResources(self):  
    try:
      # Iterate all res elements & Create / Update resource 
      resources = self.xmldoc.getElementsByTagName("res") 
      for _resource in resources:  
        _name = _resource.attributes['name'].value 
        _type = _resource.attributes['type'].value 
        # Call create function for appropriate type 
        createMethod = 'create' + _type         
        hCreateMethod = getattr(self, createMethod, None) 
        if callable(hCreateMethod):
          properties = _resource.getElementsByTagName("prop")
          hCreateMethod(_name, properties)
        else: 
          print "Create function doesn't exists for " + _type
    except:
      self.catchExcp()

  # JMS Module creation
  def createJMSModule(self, name, properties):
    p("Creating JMSModule", name)
    mbeanPath = '/JMSSystemResources/' + name
    self.wl_update()
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateJMSModule(mbean, properties, name)
    else:
      # Create the resource
      mbean = create(name, "JMSSystemResource")
      p("Update", name)
      self.updateJMSModule(mbean,properties, name)
    self.wl_activate()  
  # JMS Module - attribute update
  def updateJMSModule(self, mbean, properties, name):
    for _property in properties:
      propName = _property.attributes['name'].value
      # retrieve value
      if 'secret' in _property.attributes.keys():
          propValue = self.secret[name][propName]
      if 'value' in _property.attributes.keys():
        propValue = _property.attributes['value'].value

      if propName == "target":
        targetType = _property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- JMS module target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)
  # Server creation
  def createServer(self, name, properties):
    p("Creating Managed Server", name)
    self.wl_update()
    mbeanPath = '/Servers/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateServer(mbean,properties, name)
    else:
      # Create the resource
      mbean = create(name, "Servers")
      self.updateServer(mbean,properties, name)
    self.wl_activate()
    
  # Server - attribute update
  def updateServer(self, mbean, properties, name):
    print "--- Updating properties of Server"
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'JavaCompiler':
        mbean.setJavaCompiler(propValue)
      if propName == 'ListenAddress':
        mbean.setListenAddress(propValue)
      if propName == 'ListenPort':
        mbean.setListenPort(int(propValue))
      if propName == 'InstrumentStackTraceEnabled':
        if propValue in [ 'true', 'True', 'TRUE', 1 ]:
          propValue = True
        else:
          propValue = False
        mbean.setInstrumentStackTraceEnabled(propValue)
      if propName == 'SslEnabled':
        if propValue in [ 'true', 'True', 'TRUE', 1 ]:
          propValue = True
        else:
          propValue = False
        sslMbean = mbean.getSSL()
        sslMbean.setEnabled(propValue)
      if propName == 'SSLListenPort':
        propValue = int(propValue)
        sslMbean = mbean.getSSL()
        sslMbean.setListenPort(propValue)
      if propName == 'SslIdentityAndTrustLocations':
        sslMbean = mbean.getSSL()
        sslMbean.setIdentityAndTrustLocations(propValue)

  # JDBCDatasource creation
  def createJDBCDatasource(self, name, properties):
    p("Creating JDBC Datasource", name)
    self.wl_update()
    mbeanPath = '/JDBCSystemResources/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateJDBCDatasource(mbean,properties, name)
    else:
      # Create the resource
      mbean = create(name, "JDBCSystemResource")
      self.updateJDBCDatasource(mbean,properties, name)
    self.wl_activate()
    
  # JDBCDatasource - attribute update
  def updateJDBCDatasource(self, mbean, properties, name):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'Name':
        jdbcMbean = mbean.getJDBCResource()
        jdbcMbean.setName(propValue)
      if propName == 'ConnectionReserveTimeoutSeconds':
        jdbcMbean = mbean.getJDBCResource()
        connpoolparamMbean = jdbcMbean.getJDBCConnectionPoolParams()
        propValue = int(propValue)
        connpoolparamMbean.setConnectionReserveTimeoutSeconds(propValue)
      if propName == 'MaxCapacity':
        jdbcMbean = mbean.getJDBCResource()
        connpoolparamMbean = jdbcMbean.getJDBCConnectionPoolParams()
        propValue = int(propValue)
        connpoolparamMbean.setMaxCapacity(propValue)
      if propName == 'TestTableName':
        jdbcMbean = mbean.getJDBCResource()
        connpoolparamMbean = jdbcMbean.getJDBCConnectionPoolParams()
        connpoolparamMbean.setTestTableName(propValue)
      if propName == 'JNDIName':
        jdbcMbean = mbean.getJDBCResource()
        dsparaMbean = jdbcMbean.getJDBCDataSourceParams()
        dsparaMbean.setJNDINames([propValue])
		#modified by sankar
      #if propName == 'TwoPhaseCommit':
      #  jdbcMbean = mbean.getJDBCResource()
      #  driverparamsMbean = jdbcMbean.JDBCDataSourceParams()
      #  driverparamsMbean.setGlobalTransactionsProtocol(propValue)
		#end
      if propName == 'Url':
        jdbcMbean = mbean.getJDBCResource()
        driverparamsMbean = jdbcMbean.getJDBCDriverParams()
        driverparamsMbean.setUrl(propValue)
      if propName == 'DriverName':
        jdbcMbean = mbean.getJDBCResource()
        driverparamsMbean = jdbcMbean.getJDBCDriverParams()
        driverparamsMbean.setDriverName(propValue)
      if propName == 'Password':
        jdbcMbean = mbean.getJDBCResource()
        driverparamsMbean = jdbcMbean.getJDBCDriverParams()
        driverparamsMbean.setPassword(propValue)
      if propName == 'User':
        jdbcMbean = mbean.getJDBCResource()
        driverparamsMbean = jdbcMbean.getJDBCDriverParams()
        driverpropMbean = driverparamsMbean.getProperties() 
        userProp = driverpropMbean.lookupProperty('user')        
        if userProp == None:
          propMbean = driverpropMbean.createProperty("user")
          propMbean.setValue(propValue)
        else:
          propMbean = driverpropMbean.destroyProperty(userProp)
          propMbean = driverpropMbean.createProperty("user")
          propMbean.setValue(propValue)
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- JDBC target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)
  # SubDeployment creation
  def createSubDeployment(self, name, properties):
    p("Creating JMS Subdeployment", name)
    self.wl_update()
    jmsModule = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
    mbeanPath = '/JMSSystemResources/'+ jmsModule + '/' + 'SubDeployments/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateSubDeployment(mbean,properties, name)
    else:
      # Create the resource
      jmsPath = '/JMSSystemResources/' + jmsModule
      jmsModMbean = getMBean(jmsPath)
      mbean = jmsModMbean.createSubDeployment(name)
      self.updateSubDeployment(mbean,properties, name)
    self.wl_activate()
    
  # SubDeployment - attribute update
  def updateSubDeployment(self, mbean, properties, name):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- Subdeployment target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # ConnectionFactory creation
  def createConnectionFactory(self, name, properties):
    p("Creating Connection Factory", name)
    self.wl_update()
    jmsModule = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
        # 'JMSSystemResources', 'JMSModule', 'JMSResource', 'JMSModule', 'ConnectionFactories'
    mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/ConnectionFactories/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateConnectionFactory(mbean,properties, name, jmsModule)
    else:
      # Create the resource
      jmsPath = '/JMSSystemResources/'+jmsModule
      jmsModMbean = getMBean(jmsPath).getJMSResource()
      mbean = jmsModMbean.createConnectionFactory(name)
      self.updateConnectionFactory(mbean,properties, name, jmsModule)
    self.wl_activate()
    
  # updateConnectionFactory - attribute update
  def updateConnectionFactory(self, mbean, properties, name, jmsModule):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'JNDIName':
        mbean.setJNDIName(propValue)
      if propName == 'SubDeployment':
        mbean.setSubDeploymentName(propValue)
      if propName == 'XAConnectionFactoryEnabled':
	paramPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/' + jmsModule + '/ConnectionFactories/' + name + '/TransactionParams/' + name
	cd(paramPath)
	if propValue == 'true':
	  cmo.setXAConnectionFactoryEnabled(true)
	else:
	  cmo.setXAConnectionFactoryEnabled(false)
	cd('/')
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- ConnectionFactory target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # FileStore creation
  def createFileStore(self, name, properties):
    p("Creating Persistence Store based on Filestore", name)
    self.wl_update()
    mbeanPath = '/FileStores/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateFileStore(mbean,properties, name)
    else:
      # Create the resource
      mbean = create(name, 'FileStore')
      self.updateFileStore(mbean,properties, name)
    self.wl_activate()
    
  # FileStore - attribute update
  def updateFileStore(self, mbean, properties, name):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'Directory':
        mbean.setDirectory(propValue)
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- FileStore target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # DataStore creation
  def createDataStore(self, name, properties):
    p("Creating Persistence Store based on Datastore", name)
    self.wl_update()
    mbeanPath = '/JDBCStores/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateDataStore(mbean,properties, name)
    else:
      # Create the resource
      mbean = create(name, 'JDBCStore')
      self.updateDataStore(mbean,properties, name)
    self.wl_activate()
    
  # DataStore - attribute update
  def updateDataStore(self, mbean, properties, name):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'DataSource':
        jdbcMbean = getMBean('/JDBCSystemResources/' + propValue)
        mbean.setDataSource(jdbcMbean)
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- DataSource target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # Queue creation
  def createQueue(self, name, properties):
    p("Creating Queue", name)
    self.wl_update()
    jmsModule = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
        # 'JMSSystemResources', 'JMSModule', 'JMSResource', 'JMSModule', 'ConnectionFactories'
    mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/Queues/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateQueue(mbean,properties, name, jmsModule)
    else:
      # Create the resource
      jmsPath = '/JMSSystemResources/'+jmsModule
      jmsModMbean = getMBean(jmsPath).getJMSResource()
      mbean = jmsModMbean.createQueue(name)
      self.updateQueue(mbean,properties, name, jmsModule)
    self.wl_activate()
    
  # Queue - attribute update
  def updateQueue(self, mbean, properties, name, jmsModule):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'JNDIName':
        mbean.setJNDIName(propValue)
      if propName == 'SubDeployment':
        mbean.setSubDeploymentName(propValue)
      if propName == 'RedeliveryLimit':
        paramPath = '/JMSSystemResources/'+jmsModule+'/JMSResource/' \
          +jmsModule+'/Queues/'+name+'/DeliveryFailureParams/'+name
        cd(paramPath)
        set('RedeliveryLimit',int(propValue))
        cd('/')
      if propName == 'ErrorDestination':
        paramPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/' \
          + jmsModule + '/Queues/' + name + '/DeliveryFailureParams/' + name
        errorDestQ = '/JMSSystemResources/' + jmsModule + '/JMSResource/' \
          + jmsModule + '/Queues/' + propValue
        cd(paramPath)
        cmo.setErrorDestination(getMBean(errorDestQ))
        cd('/')
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- Queue target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # UniformDistributedQueue creation
  def createUniformDistributedQueue(self, name, properties):
    p("Creating Uniform Distributed Queue", name)
    self.wl_update()
    jmsModule = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
        # 'JMSSystemResources', 'JMSModule', 'JMSResource', 'JMSModule', 'ConnectionFactories'
    mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/UniformDistributedQueues/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateUniformDistributedQueue(mbean,properties, name, jmsModule)
    else:
      # Create the resource
      jmsPath = '/JMSSystemResources/'+jmsModule
      jmsModMbean = getMBean(jmsPath).getJMSResource()
      mbean = jmsModMbean.createUniformDistributedQueue(name)
      self.updateUniformDistributedQueue(mbean,properties, name, jmsModule)
    self.wl_activate()
    
  # UniformDistributedQueue - attribute update
  def updateUniformDistributedQueue(self, mbean, properties, name, jmsModule):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'JNDIName':
        mbean.setJNDIName(propValue)
      if propName == 'SubDeployment':
        mbean.setSubDeploymentName(propValue)
      if propName == 'RedeliveryLimit':
        paramPath = '/JMSSystemResources/'+jmsModule+'/JMSResource/' \
          +jmsModule+'/UniformDistributedQueues/'+name+'/DeliveryFailureParams/'+name
        cd(paramPath)
        set('RedeliveryLimit',int(propValue))
        cd('/')
      if propName == 'ErrorDestination':
        paramPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/' \
          + jmsModule + '/UniformDistributedQueues/' + name + '/DeliveryFailureParams/' + name
        errorDestQ = '/JMSSystemResources/' + jmsModule + '/JMSResource/' \
          + jmsModule + '/UniformDistributedQueues/' + propValue
        cd(paramPath)
        cmo.setErrorDestination(getMBean(errorDestQ))
        cd('/')
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- Queue target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # Topic creation
  def createTopic(self, name, properties):
    p("Creating Topic", name)
    self.wl_update()
    jmsModule = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
        # 'JMSSystemResources', 'JMSModule', 'JMSResource', 'JMSModule', 'ConnectionFactories'
    mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/Topics/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateTopic(mbean,properties, name)
    else:
      # Create the resource
      jmsPath = '/JMSSystemResources/'+jmsModule
      jmsModMbean = getMBean(jmsPath).getJMSResource()
      mbean = jmsModMbean.createTopic(name)
      self.updateTopic(mbean,properties, name)
    self.wl_activate()
    
  # Topic - attribute update
  def updateTopic(self, mbean, properties, name):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'JNDIName':
        mbean.setJNDIName(propValue)
      if propName == 'SubDeployment':
        mbean.setSubDeploymentName(propValue)
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- Topic target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # UniformDistributedTopic creation
  def createUniformDistributedTopic(self, name, properties):
    p("Creating Uniform Distributed Topic", name)
    self.wl_update()
    jmsModule = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
        # 'JMSSystemResources', 'JMSModule', 'JMSResource', 'JMSModule', 'ConnectionFactories'
    mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/UniformDistributedTopics/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateUniformDistributedTopic(mbean,properties, name)
    else:
      # Create the resource
      jmsPath = '/JMSSystemResources/'+jmsModule
      jmsModMbean = getMBean(jmsPath).getJMSResource()
      mbean = jmsModMbean.createUniformDistributedTopic(name)
      self.updateTopic(mbean,properties, name)
    self.wl_activate()
    
  # UniformDistributedTopic - attribute update
  def updateUniformDistributedTopic(self, mbean, properties, name):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'JNDIName':
        mbean.setJNDIName(propValue)
      if propName == 'SubDeployment':
        mbean.setSubDeploymentName(propValue)
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- Topic target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # JMSServer creation
  def createJMSServer(self, name, properties):
    p("Creating JMSServer", name)
    self.wl_update()
    mbeanPath = '/JMSServers/'+ name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateJMSServer(mbean,properties, name)
    else:
      # Create the resource
      mbean = create( name, 'JMSServer' )
      self.updateJMSServer(mbean,properties, name)
    self.wl_activate()
    
  # JMSServer - attribute update
  def updateJMSServer(self, mbean, properties, name):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'FileStore':
        cd('/JMSServers/' + name)
        set('PersistentStore', getMBean('/FileStores/' + propValue))
        cd('/')
      if propName == 'Datastore':
        cd('/JMSServers/' + name)
        set('PersistentStore', getMBean('/JDBCStores/' + propValue))
        cd('/')
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- JMSServer target: ' + propValue + ' does not exist'
        else:
          cd('/JMSServers/' + name)
          if targetType == 'Servers':
            targetType = 'Server'
          if targetType == 'Clusters':
            targetType = 'Cluster'
          target = jarray.array([ObjectName('com.bea:Name='+propValue+',Type='+targetType)], ObjectName)
          set('Targets', target)
          cd('/')
          # mbean.addTarget(targetMbean)

  # MinThreadsConstraint creation
  def createMinThreadsConstraint(self, name, properties):
    p("Creating MinThreadsConstraint", name)
    self.wl_update()
    domainname = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'domainname':
        if 'value' in property.attributes.keys():
          propValue = property.attributes['value'].value
        if 'secret' in property.attributes.keys():
          propValue = self.secret[name][propName]
        domainname = propValue
        break
    
    mbeanPath = '/SelfTuning/'+ domainname +'/MinThreadsConstraints/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateMinThreadsConstraint(mbean,properties, name, domainname)
    else:
      # Create the resource
      p('domainname', domainname)
      mbeanPath = '/SelfTuning/'+ domainname +'/MinThreadsConstraints'
      cd(mbeanPath)
      mbean = create( name, 'MinThreadsConstraints' )
      self.updateMinThreadsConstraint(mbean,properties, name, domainname)
    self.wl_activate()
  
  # MinThreadsConstraint - attribute update
  def updateMinThreadsConstraint(self, mbean, properties, name, domainname):
    domainname = ''
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'Count':
        mbean.setCount(int(propValue))
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- MinThreadsConstraint target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

  # MaxThreadsConstraint creation
  def createMaxThreadsConstraint(self, name, properties):
    p("Creating MaxThreadsConstraint", name)
    self.wl_update()
    domainname = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'domainname':
        if 'value' in property.attributes.keys():
          propValue = property.attributes['value'].value
        if 'secret' in property.attributes.keys():
          propValue = self.secret[name][propName]
        domainname = propValue
        break

    mbeanPath = '/SelfTuning/'+ domainname +'/MaxThreadsConstraints/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateMinThreadsConstraint(mbean,properties, name, domainname)
    else:
      # Create the resource
      mbeanPath = '/SelfTuning/'+ domainname +'/MaxThreadsConstraints'
      cd(mbeanPath)
      mbean = create( name, 'MaxThreadsConstraints' )
      self.updateMinThreadsConstraint(mbean,properties, name, domainname)
    self.wl_activate()
    
  # MaxThreadsConstraint - attribute update
  def updateMaxThreadsConstraint(self, mbean, properties, name, domainname):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'Count':
        mbean.setCount(int(propValue))
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- MaxThreadsConstraint target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)
  

  # Workmanager creation
  def createWorkmanager(self, name, properties):
    p("Creating Workmanager", name)
    self.wl_update()
    domainname = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'domainname':
        if 'value' in property.attributes.keys():
          propValue = property.attributes['value'].value
        if 'secret' in property.attributes.keys():
          propValue = self.secret[name][propName]
        domainname = propValue
        break

    mbeanPath = '/SelfTuning/'+ domainname +'/WorkManagers/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateWorkmanager(mbean,properties, name, domainname)
    else:
      # Create the resource
      mbeanPath = '/SelfTuning/'+ domainname +'/WorkManagers'
      cd(mbeanPath)
      mbean = create( name, 'WorkManagers' )
      self.updateWorkmanager(mbean,properties, name, domainname)
    self.wl_activate()  
  # Workmanager - attribute update
  def updateWorkmanager(self, mbean, properties, name, domainname):
    # Target has to be set first or else, setting MinThreadsConstraint & 
    # MaxThreadsConstraints will fail
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if propName == 'target':
        targetType = property.attributes['type'].value
        targetMbeanPath = '/' + targetType + '/' + propValue
        targetMbean = getMBean(targetMbeanPath)
        if targetMbean is None:
          print '--- Workmanager target: ' + propValue + ' does not exist'
        else:
          mbean.addTarget(targetMbean)

    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'Count':
        mbean.setCount(int(propValue))
      if propName == 'MinThreadsConstraint':
        cd('/SelfTuning/' + domainname + '/WorkManagers/' + name)
        minCnstBean=getMBean('/SelfTuning/' + domainname + '/MinThreadsConstraints/' + propValue)
        cmo.setMinThreadsConstraint(minCnstBean)
      if propName == 'MaxThreadsConstraint':
        cd('/SelfTuning/' + domainname + '/WorkManagers/' + name)
        maxCnstBean=getMBean('/SelfTuning/' + domainname + '/MaxThreadsConstraints/' + propValue)
        cmo.setMaxThreadsConstraint(maxCnstBean)
    cd('/')

  # Foreignserver creation
  def createForeignserver(self, name, properties):
    p("Creating Foreignserver", name)
    self.wl_update()
    jmsModule = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
    mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/ForeignServers/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateForeignserver(mbean,properties, name, jmsModule)
    else:
      # Create the resource
      jmsPath = '/JMSSystemResources/'+jmsModule
      jmsModMbean = getMBean(jmsPath).getJMSResource()
      mbean = jmsModMbean.createForeignServer(name)
      self.updateForeignserver(mbean,properties, name, jmsModule)
    self.wl_activate()
    
  # Foreignserver - attribute update
  def updateForeignserver(self, mbean, properties, name, jmsModule):
    # cd('/JMSSystemResources/' + jmsModule + '/JMSResource/' + jmsModule + '/ForeignServers/' + jmsModule)   
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'InitialContextFactory':
        p('propValue', propValue)
        mbean.setInitialContextFactory(propValue)
      if propName == 'ConnectionURL':
        mbean.setConnectionURL(propValue)
      if propName == 'JNDIPropertiesCredential':
        mbean.setJNDIPropertiesCredential(propValue)
      if propName == 'DefaultTargetingEnabled':
        if propValue in [ 'true', 'True', 'TRUE', 1 ]:
          propValue = True
        else:
          propValue = False
        mbean.setDefaultTargetingEnabled(propValue)
      if propName == 'SubDeployment':
        mbean.setSubDeploymentName(propValue)

  # ForeignserverDestination creation
  def createForeignserverDestination(self, name, properties):
    p("Creating ForeignserverDestination", name)
    self.wl_update()
    jmsModule = ''
    foreignServer = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
      if propName == 'Foreignserver':
        foreignServer = property.attributes['value'].value

    mbeanPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/'+jmsModule+ '/ForeignServers/'+foreignServer +'/ForeignDestinations/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateForeignserverDestination(mbean,properties, name, jmsModule, foreignServer)
    else:
      # Create the resource
      fsPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/'+jmsModule+ '/ForeignServers/' + foreignServer
      fsMbean = getMBean(fsPath)
      mbean = fsMbean.createForeignDestination(name)
      self.updateForeignserverDestination(mbean,properties, name, jmsModule, foreignServer)
    self.wl_activate()
    
  # ForeignserverDestination - attribute update
  def updateForeignserverDestination(self, mbean, properties, name, jmsModule, foreignServer):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'LocalJNDIName':
        mbean.setLocalJNDIName(propValue)
      if propName == 'RemoteJNDIName':
        mbean.setRemoteJNDIName(propValue)

  # ForeignserverConnectionfactory creation
  def createForeignserverConnectionfactory(self, name, properties):
    p("Creating ForeignserverConnectionfactory", name)
    self.wl_update()
    jmsModule = ''
    foreignServer = ''
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'JMSModule':
        jmsModule = property.attributes['value'].value
      if propName == 'Foreignserver':
        foreignServer = property.attributes['value'].value

    mbeanPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/'+jmsModule+ '/ForeignServers/'+foreignServer +'/ForeignConnectionFactories/' + name
    if self.pathExists(mbeanPath):
      mbean = getMBean(mbeanPath)
      self.updateForeignserverConnectionfactory(mbean,properties, name, jmsModule, foreignServer)
    else:
      # Create the resource
      fsPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/'+jmsModule+ '/ForeignServers/' + foreignServer
      fsMbean = getMBean(fsPath)
      mbean = fsMbean.createForeignDestination(name)
      self.updateForeignserverConnectionfactory(mbean,properties, name, jmsModule, foreignServer)
    self.wl_activate()
    
  # updateForeignserverConnectionfactory - attribute update
  def updateForeignserverConnectionfactory(self, mbean, properties, name, jmsModule, foreignServer):
    for property in properties:
      propName = property.attributes['name'].value
      if 'value' in property.attributes.keys():
        propValue = property.attributes['value'].value
      if 'secret' in property.attributes.keys():
        propValue = self.secret[name][propName]
      if propName == 'LocalJNDIName':
        mbean.setLocalJNDIName(propValue)
      if propName == 'RemoteJNDIName':
        mbean.setRemoteJNDIName(propValue)
      if propName == 'Username':
        mbean.setUsername(propValue)
      if propName == 'Password':
        mbean.setPassword(propValue)

  # Weblogic deployment
  def createDeploy(self, name, properties):
    p("Deploying ", name)
    self.wl_update()
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'appName':
        appName = property.attributes['value'].value
      if propName == 'earpath':
        earPath = property.attributes['value'].value
      if propName == 'target':
        targetServer = property.attributes['value'].value
        targetType = property.attributes['type'].value
      if propName == 'target1':
        targetServer1 = property.attributes['value'].value
        targetType1 = property.attributes['type'].value


    # Check if target server is in running state
    redirect('cmdStdout')
    state(targetServer)
    stopRedirect()
    fCmd = open('cmdStdout')
    lines = fCmd.readlines()
    fCmd.close()
    os.remove('cmdStdout')
    if re.search('RUNNING', lines[0]):
      deploy(appName, earPath, targetServer, timeout=0)
      deploy(appName, earPath, targetServer1, timeout=0)
    else:
      print lines[0]
      print "### Deployment of " + appName + ' was not done as the targetServer is down ###'
    self.wl_activate()
    
  def createUndeploy(self, name, properties):
    p("Undeploying ", name)
    self.wl_update()
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'appName':
        appName = property.attributes['value'].value
      if propName == 'target':
        targetServer = property.attributes['value'].value
        targetType = property.attributes['type'].value
    
    if self.pathExists('/AppDeployments/' + appName):
        undeploy(appName, timeout=60000)
    else:
      print appName + " is not deployed. So undeploy is not done"
    self.wl_activate()
    
  def createManagedserverRestart(self, name, properties):
    p("Stop, Start Managedserver", name)
    lines = domainHomePath = ''
    startTimeout = None
    startScriptName = 'start' + name + '.sh'    
    self.wl_update()
    for property in properties:
      propName = property.attributes['name'].value
      if propName == 'addLine':
        propValue = property.attributes['value'].value
        # values = propValues.split('=')
        lines += propValue + "\n"
        
      if propName == 'domainHomePath':
        domainHomePath = property.attributes['value'].value
        self.domainHomePath = domainHomePath
      
      if propName == 'startTimeout':
        startTimeout = property.attributes['value'].value
        
      if startTimeout == None:
        startTimeout = 600
        
    self.createStartupProcedure(domainHomePath, name, lines, startTimeout)
    
    # Check if managed server is in running state
    redirect('cmdStdout')
    state(name)
    stopRedirect()
    fCmd = open('cmdStdout')
    lines = fCmd.readlines()
    fCmd.close()
    os.remove('cmdStdout')
    startCmd = "cd " + domainHomePath + ";./" + startScriptName
    stopCmd = "cd " + domainHomePath + ";" + "./bin/stopManagedWebLogic.sh " + name
    if re.search('RUNNING', lines[0]):
      # Stop and Start      
      pwd = System.getProperty("user.dir")
      System.setProperty("user.dir", domainHomePath)
      p("Stopping ", name )
      o = commands.getstatusoutput(stopCmd)   
      if o[0] == 0:
        print("Server " + name + ": Stopped Successfully")
      else:
        print("Server " + name + ": Stopped Failed with exit Status: " + str(o[0]))
      p("Starting ", name)
      o = commands.getstatusoutput(startCmd)
      if o[0] == 0:
        print("Server " + name + ": Started Successfully")
      else:
        print("Server - " + name + ": Start Failed with exit Status: " + str(o[0]))
      
      System.setProperty("user.dir", pwd)
    else:
      # Start the managed servers
      pwd = System.getProperty("user.dir")
      System.setProperty("user.dir", domainHomePath)
      p("Starting ", name)
      o = commands.getstatusoutput(startCmd)
      if o[0] == 0:
        print("Server " + name + ": Started Successfully")
      else:
        print("Server - " + name + ": Start Failed with exit Status: " + str(o[0]))
      System.setProperty("user.dir", pwd)
    
  # Create startup script, Create boot.properties, Create dir to preserve startup logs
  def createStartupProcedure(self, domainHomePath, managedServerName, \
    lines, startTimeout):
    startScriptName = 'start' + managedServerName + '.sh'
    stopScriptName = 'stop' + managedServerName + '.sh'
    startupLogsPath = domainHomePath + '/startupLogs'
    
    # 1. Get connection parameters
    connection = self.xmldoc.getElementsByTagName("connection")
    connectProp = connection[0].getElementsByTagName("prop")
    user = password = host = port = ''
    for prop in connectProp:
      propName = prop.attributes['name'].value
      if 'value' in prop.attributes.keys():
        propValue = prop.attributes['value'].value
      if 'secret' in prop.attributes.keys():
        propValue = self.secret['connection'][propName]
      if propName == 'admin-user':
        user = propValue
      if propName == 'admin-password':
        password = propValue
      if propName == 'admin-host':
        host = propValue
      if propName == 'admin-port':
        port = propValue
    
    # 2. Create boot.properties if required
    self.processIdentityFile(user, password, domainHomePath, managedServerName)
    
    # 3. Create Start script
    httpAdminUrl = 'http://' + host + ':' + port 
    startScriptPath = domainHomePath + '/' + startScriptName
    chmodCmd = "chmod +x " + startScriptPath
    startScriptTxt = self.startScriptText(lines, managedServerName, \
      httpAdminUrl, startupLogsPath, startTimeout)
    if not os.path.isfile(startScriptPath):
      f = open(startScriptPath, 'w')
      f.write(startScriptTxt)
      f.close()
    else:
      os.rename(startScriptPath, startScriptPath + '.bak')
      f = open(startScriptPath, 'w')
      f.write(startScriptTxt)
      f.close()      
    os.system(chmodCmd)
    
    # 4. Create logs directory to preserve startup logs
    if not os.path.exists(startupLogsPath):
      os.makedirs(startupLogsPath)
      
  def startScriptText(self, lines, managedServerName, \
    httpAdminUrl, startupLogsPath, startTimeout):
    startScriptTxt = "#!/usr/bin/env bash\n"
    startScriptTxt += "timeout=" + str(startTimeout) + "; sleepSec=0\n"    
    startScriptTxt += lines + "\n"
    startScriptTxt += './bin/startManagedWebLogic.sh ' + managedServerName 
    startScriptTxt += ' ' + httpAdminUrl + " >" + startupLogsPath + "/" 
    startScriptTxt += managedServerName + '.log 2>&1 &' 
    startScriptTxt += "\nwhile true; do\n"
    startScriptTxt += "  if grep \"<Server started in RUNNING mode>\" "
    startScriptTxt += startupLogsPath + "/" + managedServerName + ".log 3>&1 2>&1 "
    startScriptTxt += "> /dev/null; then exit 0; \n  fi\n"  
    startScriptTxt += "  sleepSec=$((sleepSec+3))\n"
    startScriptTxt += "  if [[ \"$sleepSec\" -gt $timeout ]]; then\n"
    startScriptTxt += "    echo \"Timeout - $timeout reached, waiting for server coming to RUNNING state\"\n"
    startScriptTxt += "    echo \"Exiting ...\"\n"
    startScriptTxt += "    exit -1\n"
    startScriptTxt += "  fi\n"
    startScriptTxt += "  sleep 3;\ndone"
    return startScriptTxt
    
  def processIdentityFile(self, username, password, domainHomePath, managedServerName):
    securityPath = domainHomePath + '/servers/' + managedServerName + '/security'
    identityFilePath = securityPath + '/boot.properties'
    if not os.path.isfile(identityFilePath):
      if not os.path.exists(securityPath):
        os.makedirs(securityPath)
      identityTxt = 'username=' + username + "\npassword=" + password
      f = open(identityFilePath, 'w')
      f.write(identityTxt)
      f.close()
      
  def validateResources(self):
    try:
      # Iterate all res elements
      resources = self.xmldoc.getElementsByTagName("res") 
      for _resource in resources:  
        resName = _resource.attributes['name'].value 
        resType = _resource.attributes['type'].value
        propElements = _resource.getElementsByTagName("prop")
        self.updateReport(resType, resName, propElements)
    except:
      self.catchExcp()
      
  def updateReport(self, resType, resName, properties):
    #print resType + ":" + resName + "Report Generation"
    if resType == 'ManagedserverRestart':
      return
    if resType == 'Undeploy':
      return
    if resType == 'JMSModule':
      mbeanPath = '/JMSSystemResources/' + resName
    if resType == 'Server':
      mbeanPath = '/Servers/' + resName
    if resType == 'JDBCDatasource':
      mbeanPath = '/JDBCSystemResources/' + resName
    if resType == 'SubDeployment':
      jmsModule = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'JMSModule':
          jmsModule = property.attributes['value'].value
          mbeanPath = '/JMSSystemResources/'+ jmsModule + '/' + 'SubDeployments/' + resName
    if resType == 'ConnectionFactory':
      jmsModule = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'JMSModule':
          jmsModule = property.attributes['value'].value
      mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/ConnectionFactories/' + resName
    if resType == 'FileStore':
      mbeanPath = '/FileStores/' + resName
    if resType == 'DataStore':
      mbeanPath = '/JDBCStores/' + resName
    if resType == 'Queue':
      jmsModule = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'JMSModule':
          jmsModule = property.attributes['value'].value
      mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/Queues/' + resName
    if resType == 'Topic':
      jmsModule = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'JMSModule':
          jmsModule = property.attributes['value'].value
      mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/Topics/' + resName
    if resType == 'JMSServer':
      mbeanPath = '/JMSServers/' + resName
    if resType == 'MinThreadsConstraint':
      domainname = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'domainname':
          if 'value' in property.attributes.keys():
            propValue = property.attributes['value'].value
          if 'secret' in property.attributes.keys():
            propValue = self.secret[name][propName]
          domainname = propValue
          break
      mbeanPath = '/SelfTuning/'+ domainname +'/MinThreadsConstraints/' + resName
    if resType == 'MaxThreadsConstraint':
      domainname = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'domainname':
          if 'value' in property.attributes.keys():
            propValue = property.attributes['value'].value
          if 'secret' in property.attributes.keys():
            propValue = self.secret[name][propName]
          domainname = propValue
          break
      mbeanPath = '/SelfTuning/'+ domainname +'/MaxThreadsConstraints/' + resName
    if resType == 'Workmanager':
      domainname = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'domainname':
          if 'value' in property.attributes.keys():
            propValue = property.attributes['value'].value
          if 'secret' in property.attributes.keys():
            propValue = self.secret[name][propName]
          domainname = propValue
          break
      mbeanPath = '/SelfTuning/'+ domainname +'/WorkManagers/' + resName
    if resType == 'Foreignserver':
      jmsModule = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'JMSModule':
          jmsModule = property.attributes['value'].value
      mbeanPath = '/JMSSystemResources/'+ jmsModule + '/JMSResource/' + jmsModule + '/ForeignServers/' + resName
    if resType == 'ForeignserverDestination':
      jmsModule = ''
      foreignServer = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'JMSModule':
          jmsModule = property.attributes['value'].value
        if propName == 'Foreignserver':
          foreignServer = property.attributes['value'].value
      mbeanPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/'+jmsModule+ '/ForeignServers/'+foreignServer +'/ForeignDestinations/' + resName
    if resType == 'ForeignserverConnectionfactory':
      jmsModule = ''
      foreignServer = ''
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'JMSModule':
          jmsModule = property.attributes['value'].value
        if propName == 'Foreignserver':
          foreignServer = property.attributes['value'].value
      mbeanPath = '/JMSSystemResources/' + jmsModule + '/JMSResource/'+jmsModule+ '/ForeignServers/'+foreignServer +'/ForeignConnectionFactories/' + resName
    if resType == 'Deploy':
      for property in properties:
        propName = property.attributes['name'].value
        if propName == 'appName':
          appName = property.attributes['value'].value
        if propName == 'earpath':
          earPath = property.attributes['value'].value
        if propName == 'target':
          targetServer = property.attributes['value'].value
          targetType = property.attributes['type'].value
      redirect('cmdStdout')
      state(targetServer)
      stopRedirect()
      fCmd = open('cmdStdout')
      lines = fCmd.readlines()
      fCmd.close()
      os.remove('cmdStdout')
      if re.search('RUNNING', lines[0]):
        print "Target Server is Running"
      mbeanPath = '/AppDeployments/' + appName
    if self.pathExists(mbeanPath):
      if self.report.has_key(resType):
        self.report[resType][resName] = "Exists"
      else:
        self.report[resType] = {}
        self.report[resType][resName] = "Exists"
    else:
      if self.report.has_key(resType):
        self.report[resType][resName] = "Not Exists"
      else:
        self.report[resType] = {}
        self.report[resType][resName] = "Not Exists"
      
  def htmlReport(self):
    html = '<html>'
    html += '<head>'
    html += '<title>XML Comparision Report</title>'
    html += '<style type="text/css">'
    html += 'table.report { '
    html += 'width: 580px;'
    html += 'background-color: #fafafa;'
    html += 'border: 1px #000000 solid;'
    html += 'border-collapse: collapse;'
    html += 'border-spacing: 0px; '
    html += '}'
    html += "\n"+'td.title { '
    html += 'background-color: #99CCCC;'
    html += 'border: 1px #000000 solid;'
    html += 'font-family: Verdana;'
    html += 'font-weight: bold;'
    html += 'font-size: 12px;'
    html += 'color: #404040; '
    html += '}'
    html += "\n"+'td { '
    html += 'border: 1px #000000 solid;'
    html += 'font-family: Verdana;'
    html += 'font-size: 10px;'
    html += "}\n"
    html += '</style>'
    html += '</head>'
    html += '<body>'
    html += '<table class="report" cellspacing="0">'
    html += '<tr><td class="title" colspan="3">Weblogic Resource availability report</td></tr>'
    html += '<tr><td class="title">ResourceType</td><td class="title">Name</td><td class="title">Status</td></tr>'
    for resType in self.report.keys():
      for res in self.report[resType].keys():
        html += '<tr><td class="normal">'+resType+'</td>'
        html += '<td>'+res+'</td>'
        html += '<td>' + self.report[resType][res] + '</td></tr>'
    html += '</table></body></html>'
    if not os.path.isdir(self.reportPath):
      os.makedirs(self.reportPath)
    fPath = self.reportPath + '/' + self.reportBasename + '.html'
    f = open(fPath, 'w')
    f.write(html)
    f.close()
  
  def getPassword(self, inputInfo):
    secret = raw_input(inputInfo) 
    return secret 

  def catchExcp( self ):
    apply(traceback.print_exception, sys.exc_info())
    cancelEdit('y')
    disconnect()
    exit(exitcode=1)

validateArg()
config_xml = sys.argv[1]
wlutil = CdocmWlConfig( config_xml )