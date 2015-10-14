#!/usr/bin/python

import re
from subprocess import Popen, PIPE, STDOUT
import smtplib, string, sys, time
#import MySQLdb as mdb
import socket
#import multiprocessing

mailserver = "smtp.xxxxxxxx.com"


def MTRoute(host_list): #Function to MTR to a list of hosts, response time sla, hop count sla, packet loss sla and poll interval/count per HOST.
    MTRoute_Results = []
    for line in host_list:
        host = line[0]
        timesla = float(line[1])
        hopsla = float(line[2])
        packetlosssla = float(line[3])
        polltimes = line[4]
        polltimes = 50
        host_descript = line[5]
        cmd = '/usr/local/sbin/mtr --report -c ' + str(polltimes) + ' --interval .2 ' + host
        tracer = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)  #shell out using Popen to do traceroute cmd
        raw_results = tracer.communicate()[0]  #communicate method of Popen used to grab stdout and stderr from PIPEd above
        split_results = raw_results.split('\n')
        hopslice = int(len(split_results)) - 2
        mtr_results = split_results[hopslice]
        mtr_results_split = mtr_results.split()
        total_time = mtr_results_split[5]
        hopcount = hopslice
        packet_loss = mtr_results_split[2].strip('%')
        #find_time = re.search('(\d+.\d+)\s+ms', split_results[hopslice])
        #raw_total_time = float(find_time.group(1))
        #total_time = "%.2f" % raw_total_time 	#{0:.2f}".format(raw_total_time) #format float to 2 past decimal point 
        #hopcount = hopslice + 1
        host_tuple = (host, hopcount, total_time, packet_loss, raw_results)
        MTRoute_Results.append(host_tuple)
        total_time_sec = float(total_time) / 1000
        # --- Below Print Statements are to feed Tcollector to get metrics into OpenTSDB ----
        print('network.traceroute.response ' + str(int(time.time())) + ' ' + str(total_time_sec) + ' host=' + host)
        print('network.traceroute.hops ' + str(int(time.time())) + ' ' + str(hopcount) + ' host=' + host)
        print('network.traceroute.packetloss ' + str(int(time.time())) + ' ' + str(packet_loss) + ' host=' + host)
        #--- Below commented out as its used for native alerting if your using a local MySQL db instead of TSDB ---
        #prevrun = GetPrevRunAve_MTR_Single(host) #get previous resut average from getprevrunave function
        #print host_tuple
        #hoplowlimit = prevrun[0] * hopsla
        #timelowlimit = prevrun[1] * timesla
        #packetlosslowlimit = packetlosssla 
        #if float(hopcount) > hoplowlimit or float(total_time) > timelowlimit or float(packet_loss) > packetlosslowlimit:  #Compare results against prev run results
            #print "fail: Previous run ave was: ", prevrun[0], prevrun[1], "this run was: ", float(hopcount), float(total_time)
            #EmailAlert_MTR(host_tuple[0], float(prevrun[0]), float(prevrun[1]), prevrun[2], prevrun[3], hopcount, total_time, packet_loss, raw_results, host_descript) #FIX:  + " Traceroute Failed:  Previous run ave was: %d %d   This run was: %d %d") % (prevrun[0], prevrun[1], float(hopcount), float(total_time))
        #else:
            #print "Pass: Previous run ave was: ", prevrun[0], prevrun[1], "this run was: ", float(hopcount), float(total_time)
    return MTRoute_Results        

def WriteMTRResultsDB(result_list_to_write):
    db = mdb.connect("localhost","traceuser","traceuser123","tracedb")  #open db connection
    cursor = db.cursor()
    for each_host in result_list_to_write:
        sql = """INSERT INTO mtr_table(HOST_NAME, HOP_COUNT, TOTAL_TIME, PACKET_LOSS, RAW_RESULTS)
                 VALUES ('%s', '%d', '%s', '%s', '%s')""" % (each_host[0], each_host[1], each_host[2], each_host[3], each_host[4])
        try:
            cursor.execute(sql)
            db.commit()
        except mdb.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            sys.exit(1)

    db.close()    


def GetPrevRunAve_MTR_Single(host):
    try:
        conn = mdb.connect('localhost', 'traceuser', 'traceuser123', 'tracedb');
        cursor = conn.cursor()
        sql = "SELECT HOP_COUNT,TOTAL_TIME,TIME_STAMP,PACKET_LOSS,RAW_RESULTS FROM mtr_table WHERE HOST_NAME = '" + host + "' ORDER BY TIME_STAMP DESC LIMIT 5"
        cursor.execute(sql)
        data = cursor.fetchall()
        cursor.close()
        conn.close()

    except mdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        sys.exit(1)
    hopcounttotal = 0.0
    totaltime = 0.0
    packetlosstotal = 0.0
    prev_raw_results = ''
    for row in data:
        hopcount = row[0]
        time = row[1]
        packetloss = row[3]
        hopcounttotal += float(hopcount)
        totaltime += float(time)
        packetlosstotal += float(packetloss)
        prev_raw_results += str(row[4])
        prev_raw_results += '\n\n'
        #print(prev_raw_results)
    #print "hopcount ave:", hopcounttotal / 5.0
    #print "Time Ave: ", totaltime / 5.0
    #print "Packet Loss Ave: ", packetlosstotal / 5.0
    prevhopave = hopcounttotal / 5.0
    prevtimeave = totaltime / 5.0
    prevpacketlossave = packetlosstotal / 5.0
    #print(prev_raw_results)
    return prevhopave, prevtimeave, prevpacketlossave, prev_raw_results


def EmailAlert_MTR(alert_list, prevrunhops, prevruntime, prev_packetloss, prev_raw_results, hopcount, total_time, packetloss, current_raw_results, host_descript):  
    To = 'netops-alerts@xxxxx'
    From = 'jd-mtr@xxxxxx.com'
    if float(packetloss) > 0.0:
        Subject = str('TraceRoute Alert:  %s is experiencing PACKET LOSS!' % (alert_list))
    else:
        Subject = str('TraceRoute Alert:  %s is experiencing network issues' % (alert_list))
    Date = time.ctime(time.time())
    Header = ("From: %s\nTo: %s\nDate: %s\nSubject: %s\n\n" % (From, To, Date, Subject))
    Text = str('Host:  ' + alert_list + ' (' + host_descript + ')' + ' \n\nThe Current Poll is: \nHops: %s  \nTime: %s \nPacket Loss:  %s \n\nThe Previous 5 Poll Average was: \nHops: %s  \nTime: %s \nPacket Loss: %s \n\n The Current Poll: \n %s \n\n The Previous 5 Polls: \n %s' % (hopcount, total_time, packetloss, prevrunhops, prevruntime, prev_packetloss, current_raw_results, prev_raw_results))
    print(Text)
    server = smtplib.SMTP(mailserver, 25)
    failed = server.sendmail(From, To, Header + Text)
    server.quit()
    if failed:
        print("failed to send mail")
    else:
        print("all done sending")



def TraceRoute(host_list): # OLD - (replaced by MTR) Function to traceroute to a list of hosts, splits results, returns back list of tuples for host,hopcount and time for each host
    TraceRoute_Results = []
    for host in host_list:
        cmd = 'traceroute -q 1 -I ' + host
        tracer = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)  #shell out using Popen to do traceroute cmd
        raw_results = tracer.communicate()[0]  #communicate method of Popen used to grab stdout and stderr from PIPEd above
        split_results = raw_results.split('\n')
        hopslice = int(len(split_results)) - 2
        print(split_results[hopslice])
        find_time = re.search('(\d+.\d+)\s+ms', split_results[hopslice])
        raw_total_time = float(find_time.group(1))
        total_time = "%.2f" % raw_total_time 	#{0:.2f}".format(raw_total_time) #format float to 2 past decimal point 
        hopcount = hopslice + 1
        host_tuple = (host, hopcount, total_time, raw_results)
        TraceRoute_Results.append(host_tuple)
        prevrun = GetPrevRunAve_Single(host) #get previous resut average from getprevrunave function
        print host_tuple
        hoplowlimit = prevrun[0] * 1.5
        timelowlimit = prevrun[1] * 2.0
        if float(hopcount) > hoplowlimit or float(total_time) > timelowlimit:  #Compare results against prev run results
            print "fail: Previous run ave was: ", prevrun[0], prevrun[1], "this run was: ", float(hopcount), float(total_time)
            EmailAlert(host_tuple[0], float(prevrun[0]), float(prevrun[1]), hopcount, total_time, raw_results, prevrun[2]) #FIX:  + " Traceroute Failed:  Previous run ave was: %d %d   This run was: %d %d") % (prevrun[0], prevrun[1], float(hopcount), float(total_time))
        else:
            print "Pass: Previous run ave was: ", prevrun[0], prevrun[1], "this run was: ", float(hopcount), float(total_time)
    return TraceRoute_Results        
        


def WriteTraceFiles(result_list_to_write):
    for each_host in result_list_to_write:
        file = open(each_host[0], 'a')
        results_entry = str(each_host[1]) + ',' + str(each_host[2]) + '\n'
        file.write(results_entry)
        file.close()


def WriteResultsDB(result_list_to_write):
    db = mdb.connect("localhost","traceuser","traceuser123","tracedb")  #open db connection
    cursor = db.cursor()
    for each_host in result_list_to_write:
        sql = """INSERT INTO trace_table(HOST_NAME, HOP_COUNT, TOTAL_TIME, RAW_RESULTS)
                 VALUES ('%s', '%d', '%s', '%s')""" % (each_host[0], each_host[1], each_host[2], each_host[3])
        try:
            cursor.execute(sql)
            db.commit()
        except mdb.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            sys.exit(1)

    db.close()    

def GetPreviousResults(host_list): #Loop through the last 5 runs of each host, ave the hops/time out and return dictionaries back for later comparison
    last_run_hop_ave = {}
    last_run_time_ave = {}
    conn = mdb.connect('localhost', 'traceuser', 'traceuser123', 'tracedb');
    cursor = conn.cursor()
    for host in host_list:
        try:
            sql = "SELECT HOP_COUNT,TOTAL_TIME,TIME_STAMP FROM trace_table WHERE HOST_NAME = '" + host + "' ORDER BY TIME_STAMP DESC LIMIT 5"
            print sql
            cursor.execute(sql)
            data = cursor.fetchall()
            hopcounttotal = 0.0
            totaltime = 0.0
            for row in data:
                 hopcount = row[0]
                 time = row[1]
                 hopcounttotal += float(hopcount)
                 totaltime += float(time)
            hopave = hopcounttotal / 5.0
            timeave = totaltime / 5.0
            last_run_hop_ave[host] = hopave
            last_run_time_ave[host] = timeave
        except mdb.Error, e:
            print "Error %d: %s" % (e.args[0], e.args[1])
            sys.exit(1)
    cursor.close()
    conn.close()
    return last_run_hop_ave, last_run_time_ave

def GetPrevRunAve_Single(host):
    try:
        conn = mdb.connect('localhost', 'traceuser', 'traceuser123', 'tracedb');
        cursor = conn.cursor()
        sql = "SELECT HOP_COUNT,TOTAL_TIME,TIME_STAMP,RAW_RESULTS FROM trace_table WHERE HOST_NAME = '" + host + "' ORDER BY TIME_STAMP DESC LIMIT 5"
        cursor.execute(sql)
        data = cursor.fetchall()
        cursor.close()
        conn.close()

    except mdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        sys.exit(1)
    hopcounttotal = 0.0
    totaltime = 0.0
    prev_raw_results = ''
    for row in data:
        hopcount = row[0]
        time = row[1]
        hopcounttotal += float(hopcount)
        totaltime += float(time)
        prev_raw_results += str(row[3])
        prev_raw_results += '\n\n'
        #print(prev_raw_results)
    print "hopcount ave:", hopcounttotal / 5.0
    print "Time Ave: ", totaltime / 5.0
    prevhopave = hopcounttotal / 5.0
    prevtimeave = totaltime / 5.0
    #print(prev_raw_results)
    return prevhopave, prevtimeave, prev_raw_results

def CompareResults_FileBased(host_list):  #Loop each host file to compare last 5 polls to current poll and return back alert_list of alertable hosts and hops/times
    alert_list = []
    for host in host_list:
        all_polls = open(host).read().splitlines()
        result_list = []
        for result_set in all_polls: #Get all polls from file into list then split into sublist pairs on comma
            tuple = result_set.split(",")
            result_list.append(tuple)
        result_count = len(result_list)    
        #set defaults
        hop = 0
        time = 0.0
        alert = False
        for each_result in result_list[result_count - 6:result_count -1]:  #Parse last x previous results and average them out
            x = 5
            hop = hop + int(each_result[0])
            hop_ave = float(hop / x)
            time = time + float(each_result[1])
            time_ave = time / x
        current_hop = int(result_list[result_count - 1][0])
        current_time = float(result_list[result_count - 1][1])
        if current_hop > int(hop_ave * 0.1):
            alert = True
            print('ALERT: Current Hop is: ', current_hop, 'Last 5 Average was: ', hop_ave)
        if current_time > float(time_ave * 0.1):
            alert = True
            print('ALERT: Current Time is: ',  "{0:.2f}".format(current_time), 'Last 5 Average was: ',  "{0:.2f}".format(time_ave))
        if alert == True:
            alert_entry = (host, current_hop, current_time, hop_ave, time_ave)
            alert_list.append(alert_entry)
    return alert_list    


def EmailAlert(alert_list, prevrunhops, prevruntime, hopcount, total_time, current_raw_results, prev_raw_results):  
    To = 'jd@xxxxx.com'
    From = 'jd@xxxxxxx.com'
    Subject = 'TraceRoute Alert: Our network  has traceroute anomolies'
    Date = time.ctime(time.time())
    Header = ("From: %s\nTo: %s\nDate: %s\nSubject: %s\n\n" % (From, To, Date, Subject))
    Text = str(alert_list + ' Previous 5 Poll average was: Hops: %s  Time: %s and Current Poll is: Hops: %s  Time: %s \n\n The Current Poll: \n %s \n\n The Previous 5 Polls: \n %s' % (prevrunhops, prevruntime, hopcount, total_time, current_raw_results, prev_raw_results))
    print(Text)
    server = smtplib.SMTP(mailserver, 587)
    failed = server.sendmail(From, To, Header + Text)
    server.quit()
    if failed:
        print("failed to send mail")
    else:
        print("all done sending")

def ImportHostList():
    Host_List = []
    f = open('/home/jdean/host_list_mtr_opentsdb.txt', 'r')
    lines = f.readlines()
    for line in lines:
      entry = line.strip('\n').split(',')
      Host_List.append(entry)
    Host_List.remove(Host_List[0])
    return Host_List
        
def main():
    # --- Use below host_list_input for quick static list -- comment out and use ImportHostList() is preferred ---
    host_list_input = [('google.com', 5, 20, 20, 20, 'google site'), ('4.2.2.2',5,5,5,5,'test node') ]
    #if socket.gethostname() != 'netprobe001.xxx.xxxx':  #use if running a distributed Tcollector archicture
    #    sys.exit(3)
    while True:
        # host_list_input = ImportHostList()
    #print GetPreviousResults(host_list_input)
        resultlist = MTRoute(host_list_input)
    #print resultlist
    #WriteTraceFiles(resultlist)
        #WriteMTRResultsDB(resultlist)
        time.sleep(10)
    #alert_list = CompareResults_FileBased(host_list_input)
    #EmailAlert(alert_list)
    #sys.exit(1) use for nagios

main()



