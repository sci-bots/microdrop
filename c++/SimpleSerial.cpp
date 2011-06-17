/*
 * File:   SimpleSerial.cpp
 * Author: Terraneo Federico
 * Distributed under the Boost Software License, Version 1.0.
 * Created on September 7, 2009, 10:46 AM
 *
 * IMPORTANT:
 * On Mac OS X boost asio's serial ports have bugs, and the usual implementation
 * of this class does not work. So a workaround class was written temporarily,
 * until asio (hopefully) will fix Mac compatibility for serial ports.
 *
 * Please note that unlike said in the documentation on OS X until asio will
 * be fixed serial port *writes* are *not* asynchronous, but at least
 * asynchronous *read* works.
 * In addition the serial port open ignores the following options: parity,
 * character size, flow, stop bits, and defaults to 8N1 format.
 * I know it is bad but at least it's better than nothing.
 *
 */

#include "SimpleSerial.h"

#include <string>
#include <algorithm>
#include <iostream>
#include <boost/bind.hpp>

using namespace std;
using namespace boost;

#ifndef __APPLE__

class SimpleSerialImpl: private boost::noncopyable
{
public:
    SimpleSerialImpl(): io(), port(io), backgroundThread(), open(false),
            error(false) {}

    boost::asio::io_service io; ///< Io service object
    boost::asio::serial_port port; ///< Serial port object
    boost::thread backgroundThread; ///< Thread that runs read/write operations
    bool open; ///< True if port open
    bool error; ///< Error flag
    mutable boost::mutex errorMutex; ///< Mutex for access to error

    /// Data are queued here before they go in writeBuffer
    std::vector<char> writeQueue;
    boost::shared_array<char> writeBuffer; ///< Data being written
    size_t writeBufferSize; ///< Size of writeBuffer
    boost::mutex writeQueueMutex; ///< Mutex for access to writeQueue
    char readBuffer[SimpleSerial::readBufferSize]; ///< data being read

    /// Read complete callback
    boost::function<void (const char*, size_t)> callback;
};

SimpleSerial::SimpleSerial(): pimpl(new SimpleSerialImpl)
{
    setReadCallback(boost::bind(&SimpleSerial::readCallback, this, _1, _2));
}

SimpleSerial::SimpleSerial(const std::string& devname,
        unsigned int baud_rate,
        asio::serial_port_base::parity opt_parity,
        asio::serial_port_base::character_size opt_csize,
        asio::serial_port_base::flow_control opt_flow,
        asio::serial_port_base::stop_bits opt_stop)
        : pimpl(new SimpleSerialImpl)
{
    begin(devname,baud_rate,opt_parity,opt_csize,opt_flow,opt_stop);
    setReadCallback(boost::bind(&SimpleSerial::readCallback, this, _1, _2));
}

bool SimpleSerial::begin(const std::string& devname, unsigned int baud_rate,
        asio::serial_port_base::parity opt_parity,
        asio::serial_port_base::character_size opt_csize,
        asio::serial_port_base::flow_control opt_flow,
        asio::serial_port_base::stop_bits opt_stop)
{
  try {
    if(isOpen()) end();
    setErrorStatus(true);//If an exception is thrown, error_ remains true
    pimpl->port.open(devname);
    pimpl->port.set_option(asio::serial_port_base::baud_rate(baud_rate));
    pimpl->port.set_option(opt_parity);
    pimpl->port.set_option(opt_csize);
    pimpl->port.set_option(opt_flow);
    pimpl->port.set_option(opt_stop);

    //This gives some work to the io_service before it is started
    pimpl->io.post(boost::bind(&SimpleSerial::doRead, this));
    thread t(boost::bind(&asio::io_service::run, &pimpl->io));
    pimpl->backgroundThread.swap(t);
    setErrorStatus(false);//If we get here, no error
    pimpl->open=true; //Port is now open
  } catch(...) {

  }
  return errorStatus();
}

bool SimpleSerial::isOpen() const
{
    return pimpl->open;
}

bool SimpleSerial::errorStatus() const
{
    lock_guard<mutex> l(pimpl->errorMutex);
    return pimpl->error;
}

void SimpleSerial::end()
{
    if(!isOpen()) return;

    pimpl->open=false;
    pimpl->io.post(boost::bind(&SimpleSerial::doClose, this));
    pimpl->backgroundThread.join();
    pimpl->io.reset();
    this_thread::sleep(posix_time::milliseconds(200));
    if(errorStatus())
    {
        throw(boost::system::system_error(boost::system::error_code(),
                "Error while closing the device"));
    }
}

void SimpleSerial::write(const char data)
{
    {
        lock_guard<mutex> l(pimpl->writeQueueMutex);
        pimpl->writeQueue.push_back(data);
    }
    pimpl->io.post(boost::bind(&SimpleSerial::doWrite, this));
}

void SimpleSerial::write(const char *data, size_t size)
{
    {
        lock_guard<mutex> l(pimpl->writeQueueMutex);
        pimpl->writeQueue.insert(pimpl->writeQueue.end(),data,data+size);
    }
    pimpl->io.post(boost::bind(&SimpleSerial::doWrite, this));
}

void SimpleSerial::write(const std::vector<char>& data)
{
    {
        lock_guard<mutex> l(pimpl->writeQueueMutex);
        pimpl->writeQueue.insert(pimpl->writeQueue.end(),data.begin(),
                data.end());
    }
    pimpl->io.post(boost::bind(&SimpleSerial::doWrite, this));
}

void SimpleSerial::print(const std::string& s)
{
    {
        lock_guard<mutex> l(pimpl->writeQueueMutex);
        pimpl->writeQueue.insert(pimpl->writeQueue.end(),s.begin(),s.end());
    }
    pimpl->io.post(boost::bind(&SimpleSerial::doWrite, this));
}

void SimpleSerial::println(const std::string& s)
{
    {
        lock_guard<mutex> l(pimpl->writeQueueMutex);
        pimpl->writeQueue.insert(pimpl->writeQueue.end(),s.begin(),s.end());
        pimpl->writeQueue.push_back('\n');
    }
    pimpl->io.post(boost::bind(&SimpleSerial::doWrite, this));
}

SimpleSerial::~SimpleSerial()
{
    if(isOpen())
    {
        try {
            end();
        } catch(...)
        {
            //Don't throw from a destructor
        }
    }
    clearReadCallback();
}

void SimpleSerial::doRead()
{
    pimpl->port.async_read_some(asio::buffer(pimpl->readBuffer,readBufferSize),
            boost::bind(&SimpleSerial::readEnd,
            this,
            asio::placeholders::error,
            asio::placeholders::bytes_transferred));
}

void SimpleSerial::readEnd(const boost::system::error_code& error,
        size_t bytes_transferred)
{
    if(error)
    {
        #ifdef __APPLE__
        if(error.value()==45)
        {
            //Bug on OS X, it might be necessary to repeat the setup
            //http://osdir.com/ml/lib.boost.asio.user/2008-08/msg00004.html
            doRead();
            return;
        }
        #endif //__APPLE__
        //error can be true even because the serial port was closed.
        //In this case it is not a real error, so ignore
        if(isOpen())
        {
            doClose();
            setErrorStatus(true);
        }
    } else {
        if(pimpl->callback) pimpl->callback(pimpl->readBuffer,
                bytes_transferred);
        doRead();
    }
}

void SimpleSerial::doWrite()
{
    //If a write operation is already in progress, do nothing
    if(pimpl->writeBuffer==0)
    {
        lock_guard<mutex> l(pimpl->writeQueueMutex);
        pimpl->writeBufferSize=pimpl->writeQueue.size();
        pimpl->writeBuffer.reset(new char[pimpl->writeQueue.size()]);
        copy(pimpl->writeQueue.begin(),pimpl->writeQueue.end(),
                pimpl->writeBuffer.get());
        pimpl->writeQueue.clear();
        async_write(pimpl->port,asio::buffer(pimpl->writeBuffer.get(),
                pimpl->writeBufferSize),
                boost::bind(&SimpleSerial::writeEnd, this, asio::placeholders::error));
    }
}

void SimpleSerial::writeEnd(const boost::system::error_code& error)
{
    if(!error)
    {
        lock_guard<mutex> l(pimpl->writeQueueMutex);
        if(pimpl->writeQueue.empty())
        {
            pimpl->writeBuffer.reset();
            pimpl->writeBufferSize=0;

            return;
        }
        pimpl->writeBufferSize=pimpl->writeQueue.size();
        pimpl->writeBuffer.reset(new char[pimpl->writeQueue.size()]);
        copy(pimpl->writeQueue.begin(),pimpl->writeQueue.end(),
                pimpl->writeBuffer.get());
        pimpl->writeQueue.clear();
        async_write(pimpl->port,asio::buffer(pimpl->writeBuffer.get(),
                pimpl->writeBufferSize),
                boost::bind(&SimpleSerial::writeEnd, this, asio::placeholders::error));
    } else {
        setErrorStatus(true);
        doClose();
    }
}

void SimpleSerial::doClose()
{
    boost::system::error_code ec;
    pimpl->port.cancel(ec);
    if(ec) setErrorStatus(true);
    pimpl->port.close(ec);
    if(ec) setErrorStatus(true);
}

void SimpleSerial::setErrorStatus(bool e)
{
    lock_guard<mutex> l(pimpl->errorMutex);
    pimpl->error=e;
}

void SimpleSerial::setReadCallback(const
        boost::function<void (const char*, size_t)>& callback)
{
    pimpl->callback=callback;
}

void SimpleSerial::clearReadCallback()
{
    pimpl->callback.clear();
}

#else //__APPLE__

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

class SimpleSerialImpl: private boost::noncopyable
{
public:
    SimpleSerialImpl(): backgroundThread(), open(false), error(false) {}

    boost::thread backgroundThread; ///< Thread that runs read operations
    bool open; ///< True if port open
    bool error; ///< Error flag
    mutable boost::mutex errorMutex; ///< Mutex for access to error

    int fd; ///< File descriptor for serial port

    char readBuffer[SimpleSerial::readBufferSize]; ///< data being read

    /// Read complete callback
    boost::function<void (const char*, size_t)> callback;
};

SimpleSerial::SimpleSerial(): pimpl(new SimpleSerialImpl)
{

}

SimpleSerial::SimpleSerial(const std::string& devname, unsigned int baud_rate,
        asio::serial_port_base::parity opt_parity,
        asio::serial_port_base::character_size opt_csize,
        asio::serial_port_base::flow_control opt_flow,
        asio::serial_port_base::stop_bits opt_stop)
        : pimpl(new SimpleSerialImpl)
{
    begin(devname,baud_rate,opt_parity,opt_csize,opt_flow,opt_stop);
}

bool SimpleSerial::begin(const std::string& devname, unsigned int baud_rate,
        asio::serial_port_base::parity opt_parity,
        asio::serial_port_base::character_size opt_csize,
        asio::serial_port_base::flow_control opt_flow,
        asio::serial_port_base::stop_bits opt_stop)
{
  try {
    if(isOpen()) end();

    setErrorStatus(true);//If an exception is thrown, error remains true

    struct termios new_attributes;
    speed_t speed;
    int status;

    // Open port
    pimpl->fd=::begin(devname.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (pimpl->fd<0) throw(boost::system::system_error(
            boost::system::error_code(),"Failed to open port"));

    // Set Port parameters.
    status=tcgetattr(pimpl->fd,&new_attributes);
    if(status<0  || !isatty(pimpl->fd))
    {
        ::end(pimpl->fd);
        throw(boost::system::system_error(
                    boost::system::error_code(),"Device is not a tty"));
    }
    new_attributes.c_iflag = IGNBRK;
    new_attributes.c_oflag = 0;
    new_attributes.c_lflag = 0;
    new_attributes.c_cflag = (CS8 | CREAD | CLOCAL);//8 data bit,Enable receiver,Ignore modem
    /* In non canonical mode (Ctrl-C and other disabled, no echo,...) VMIN and VTIME work this way:
    if the function read() has'nt read at least VMIN chars it waits until has read at least VMIN
    chars (even if VTIME timeout expires); once it has read at least vmin chars, if subsequent
    chars do not arrive before VTIME expires, it returns error; if a char arrives, it resets the
    timeout, so the internal timer will again start from zero (for the nex char,if any)*/
    new_attributes.c_cc[VMIN]=1;// Minimum number of characters to read before returning error
    new_attributes.c_cc[VTIME]=1;// Set timeouts in tenths of second

    // Set baud rate
    switch(baud_rate)
    {
        case 50:speed= B50; break;
        case 75:speed= B75; break;
        case 110:speed= B110; break;
        case 134:speed= B134; break;
        case 150:speed= B150; break;
        case 200:speed= B200; break;
        case 300:speed= B300; break;
        case 600:speed= B600; break;
        case 1200:speed= B1200; break;
        case 1800:speed= B1800; break;
        case 2400:speed= B2400; break;
        case 4800:speed= B4800; break;
        case 9600:speed= B9600; break;
        case 19200:speed= B19200; break;
        case 38400:speed= B38400; break;
        case 57600:speed= B57600; break;
        case 115200:speed= B115200; break;
        case 230400:speed= B230400; break;
        default:
        {
            ::end(pimpl->fd);
            throw(boost::system::system_error(
                        boost::system::error_code(),"Unsupported baud rate"));
        }
    }

    cfsetospeed(&new_attributes,speed);
    cfsetispeed(&new_attributes,speed);

    //Make changes effective
    status=tcsetattr(pimpl->fd, TCSANOW, &new_attributes);
    if(status<0)
    {
        ::end(pimpl->fd);
        throw(boost::system::system_error(
                    boost::system::error_code(),"Can't set port attributes"));
    }

    //These 3 lines clear the O_NONBLOCK flag
    status=fcntl(pimpl->fd, F_GETFL, 0);
    if(status!=-1) fcntl(pimpl->fd, F_SETFL, status & ~O_NONBLOCK);

    setErrorStatus(false);//If we get here, no error
    pimpl->open=true; //Port is now open

    thread t(boost::bind(&SimpleSerial::doRead, this));
    pimpl->backgroundThread.swap(t);
  } catch(...) {
  }
  return errorStatus();
}

bool SimpleSerial::isOpen() const
{
    return pimpl->open;
}

bool SimpleSerial::errorStatus() const
{
    lock_guard<mutex> l(pimpl->errorMutex);
    return pimpl->error;
}

void SimpleSerial::end()
{
    if(!isOpen()) return;

    pimpl->open=false;

    ::end(pimpl->fd); //The thread waiting on I/O should return

    pimpl->backgroundThread.join();
    if(errorStatus())
    {
        throw(boost::system::system_error(boost::system::error_code(),
                "Error while closing the device"));
    }
}

void SimpleSerial::write(const char data)
{
    if(::write(pimpl->fd,&data,1)!=1) setErrorStatus(true);
}

void SimpleSerial::write(const char *data, size_t size)
{
    if(::write(pimpl->fd,data,size)!=size) setErrorStatus(true);
}

void SimpleSerial::write(const std::vector<char>& data)
{
    if(::write(pimpl->fd,&data[0],data.size())!=data.size())
        setErrorStatus(true);
}

void SimpleSerial::print(const std::string& s)
{
    if(::write(pimpl->fd,&s[0],s.size())!=s.size()) setErrorStatus(true);
}

void SimpleSerial::println(std::string& s)
{
    string t = s;
    t.append("\n");
    if(::write(pimpl->fd,&t[0],t.size())!=t.size()+1) setErrorStatus(true);
}

SimpleSerial::~SimpleSerial()
{
    if(isOpen())
    {
        try {
            end();
        } catch(...)
        {
            //Don't throw from a destructor
        }
    }
}

void SimpleSerial::doRead()
{
    //Read loop in spawned thread
    for(;;)
    {
        int received=::read(pimpl->fd,pimpl->readBuffer,readBufferSize);
        if(received<0)
        {
            if(isOpen()==false) return; //Thread interrupted because port closed
            else {
                setErrorStatus(true);
                continue;
            }
        }
        if(pimpl->callback) pimpl->callback(pimpl->readBuffer, received);
    }
}

void SimpleSerial::readEnd(const boost::system::error_code& error,
        size_t bytes_transferred)
{
    //Not used
}

void SimpleSerial::doWrite()
{
    //Not used
}

void SimpleSerial::writeEnd(const boost::system::error_code& error)
{
    //Not used
}

void SimpleSerial::doClose()
{
    //Not used
}

void SimpleSerial::setErrorStatus(bool e)
{
    lock_guard<mutex> l(pimpl->errorMutex);
    pimpl->error=e;
}

void SimpleSerial::setReadCallback(const
        boost::function<void (const char*, size_t)>& callback)
{
    pimpl->callback=callback;
}

void SimpleSerial::clearReadCallback()
{
    pimpl->callback.clear();
}

#endif //__APPLE__

void SimpleSerial::flush()
{
    lock_guard<mutex> l(readQueueMutex);
    readQueue.clear();
}

size_t SimpleSerial::available()
{
    lock_guard<mutex> l(readQueueMutex);
    return readQueue.size();
}

char SimpleSerial::read()
{
    lock_guard<mutex> l(readQueueMutex);
    char c=-1;
    if(readQueue.size()>0) {
      c = readQueue.front();
      readQueue.erase(readQueue.begin());
    }
    return c;
}

size_t SimpleSerial::read(char *data, size_t size)
{
    lock_guard<mutex> l(readQueueMutex);
    size_t result=min(size,readQueue.size());
    vector<char>::iterator it=readQueue.begin()+result;
    copy(readQueue.begin(),it,data);
    readQueue.erase(readQueue.begin(),it);
    return result;
}

std::vector<char> SimpleSerial::readAll()
{
    lock_guard<mutex> l(readQueueMutex);
    vector<char> result;
    result.swap(readQueue);
    return result;
}

std::string SimpleSerial::readString()
{
    lock_guard<mutex> l(readQueueMutex);
    string result(readQueue.begin(),readQueue.end());
    readQueue.clear();
    return result;
}

std::string SimpleSerial::readStringUntil(const std::string delim)
{
    lock_guard<mutex> l(readQueueMutex);
    vector<char>::iterator it=findStringInVector(readQueue,delim);
    if(it==readQueue.end()) return "";
    string result(readQueue.begin(),it);
    it+=delim.size();//Do remove the delimiter from the queue
    readQueue.erase(readQueue.begin(),it);
    return result;
}

void SimpleSerial::readCallback(const char *data, size_t len)
{
    lock_guard<mutex> l(readQueueMutex);
    readQueue.insert(readQueue.end(),data,data+len);
}

std::vector<char>::iterator SimpleSerial::findStringInVector(
        std::vector<char>& v,const std::string& s)
{
    if(s.size()==0) return v.end();

    vector<char>::iterator it=v.begin();
    for(;;)
    {
        vector<char>::iterator result=find(it,v.end(),s[0]);
        if(result==v.end()) return v.end();//If not found return

        for(size_t i=0;i<s.size();i++)
        {
            vector<char>::iterator temp=result+i;
            if(temp==v.end()) return v.end();
            if(s[i]!=*temp) goto mismatch;
        }
        //Found
        return result;

        mismatch:
        it=result+1;
    }
}
