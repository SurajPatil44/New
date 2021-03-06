from socket import *
import select,sys,time
import queue
import struct
import time
from threading import Thread
from multiprocessing import Process
from threading import Lock
import json
import numpy as np
import cv2

def valueBar(value,start,end,val_len=20):
    inmb = (value / (8 *1024*1024))
    value = inmb / (end - start)
    val = str(value) + ' MBps'
    spaces = ' ' * (val_len - len(val))
    sys.stdout.write(f"\rSpeed : [{val+spaces}]")
    sys.stdout.flush()

sock = socket(AF_INET,SOCK_STREAM)
sock.setblocking(0)
sock.bind(('localhost',6030))
sock.listen(5)

class LargeFileServer:
    
    def __init__(self,sock):
        self.sock = sock
        self.msg_q = {}
        self.data_que = queue.Queue()
        self.inputs = [sock]
        self.outputs = []
        self.cur_ind = None
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.total = 0
        #self.ht = None
        #self.wd = None

    def recv_msg(self,sock):
        initinfo = self.recvall(8,sock)
        #print(initinfo)
        if not initinfo:
            return None
        ind,msglen = struct.unpack('ii',initinfo)
        self.cur_ind = ind
        return self.recvall(msglen,sock)

    def recvall(self,size,sock):
        data = b''
        while (len(data) < size):
            packet = sock.recv(size - len(data))
            #print(packet)
            if not packet:
                return None
            data += packet
        return data

    def start_serving(self): 
        while self.inputs:
            readable,writable,exceptional = select.select(self.inputs,self.outputs,self.inputs)
            #print([_s.fileno() for _s in self.inputs])
	            #print(f'READ : {readable}')
	            #print(f'WRITE : {writable}')
	            #print(f'EXCEPT : {exceptional}')
            for s in readable:
                if s is sock:
                    conn,addr = s.accept()
                    conn.setblocking(1)
                    #############################################################################################
                    ##LESSON :: Keeping the setblocking 0 will fetch data as soon as connection established    ##
                    ##          which gives nothing(buffer is empty (i.e. EAGAIN )) so need to keep setblocking## 
                    ##          1. Need to see behaviour for multiple clients.                                 ##
                    ############################################################################################# 
                    self.inputs.append(conn)
                    self.msg_q[conn] = queue.Queue()
                else:
                ####NEED TO CHECK THIS KEEPS CHECKING DATA IN DIFFERENT THREAD###
                    try:
                        start = time.time()
                        _data = self.recv_msg(s)
                        
                        #print(f"{len(_data)}")
                        if _data:
                            end = time.time()
                            self.total += len(_data)
                            valueBar(len(_data),start,end)
                            self.msg_q[s].put(_data)
                            if s not in self.outputs:
                                self.outputs.append(s)
                        else:
                            if s in self.outputs:
                                self.outputs.remove(s)
                            else:       
                                self.inputs.remove(s)
                            s.close()
                            print("CLOSED AT 1")
                            del self.msg_q[s]
                    except Exception as e:
                        print(f"Exception is {e}")
                        

            for s in writable:
		      
                try:
                    next_msg = self.msg_q[s].get_nowait()
                    if next_msg:
                        self.data_que.put(next_msg) 
		                #print(f'{next_msg}')
                except queue.Empty:
		                #print(f"Exception is {e}
                    self.outputs.remove(s)
                except Exception as e:
                    print(f"STOPPING HERE DUE TO {e}") 
                else:
                    #recved = json.loads(next_msg)
                    #ind,_ = struct.unpack('ii',recved['size'].encode('latin-1'))
                    msg = f'received {self.cur_ind}'
                    s.send(msg.encode())

            for s in exceptional:
                self.inputs.remove(s)
                if s in self.outputs:
                    self.outputs.remove(s)
                s.close()
                print("CLOSED AT 2")
                del self.msg_q[s]

    def stream_video(self):
        while True:
            framebytes = self.data_que.get()
            #print(len(framebytes))
            numpy_arr = np.frombuffer(framebytes,dtype='uint8')
            #print(numpy_arr.shape)
            frame = numpy_arr.reshape((480,640,3))
            fps = time.time() - START
            frame = cv2.putText(frame,str(fps),(230,350),self.font,1,(255,0,0),2,cv2.LINE_AA)
            #frame2 = frame2.resize((480,640))
            cv2.imshow('streamer',frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                pass
    
    def run(self):
        Thread(target=self.start_serving).start()
        Thread(target=self.stream_video).start()



msgser = LargeFileServer(sock)
START = time.time()
try:
    msgser.run()
except:
    cv2.destroyAllWindows()

