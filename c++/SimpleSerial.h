/*
 * File:   SimpleSerial.h
 * Author: Terraneo Federico
 * Distributed under the Boost Software License, Version 1.0.
 * Created on September 7, 2009, 10:46 AM
 */

#ifndef _SIMPLESERIAL_H
#define	_SIMPLESERIAL_H

#include <vector>
#include <boost/asio.hpp>
#include <boost/thread.hpp>
#include <boost/utility.hpp>
#include <boost/function.hpp>
#include <boost/shared_array.hpp>

class SimpleSerialImpl;

class SimpleSerial: private boost::noncopyable
{
public:
    SimpleSerial();

    /**
    * Opens a serial device.
    * \param devname serial device name, example "/dev/ttyS0" or "COM1"
    * \param baud_rate serial baud rate
    * \param opt_parity serial parity, default none
    * \param opt_csize serial character size, default 8bit
    * \param opt_flow serial flow control, default none
    * \param opt_stop serial stop bits, default 1
    * \throws boost::system::system_error if cannot open the
    * serial device
    */
    SimpleSerial(const std::string& devname, unsigned int baud_rate,
        boost::asio::serial_port_base::parity opt_parity=
            boost::asio::serial_port_base::parity(
                boost::asio::serial_port_base::parity::none),
        boost::asio::serial_port_base::character_size opt_csize=
            boost::asio::serial_port_base::character_size(8),
        boost::asio::serial_port_base::flow_control opt_flow=
            boost::asio::serial_port_base::flow_control(
                boost::asio::serial_port_base::flow_control::none),
        boost::asio::serial_port_base::stop_bits opt_stop=
            boost::asio::serial_port_base::stop_bits(
                boost::asio::serial_port_base::stop_bits::one));

    /**
    * Opens a serial device.
    * \param devname serial device name, example "/dev/ttyS0" or "COM1"
    * \param baud_rate serial baud rate
    * \param opt_parity serial parity, default none
    * \param opt_csize serial character size, default 8bit
    * \param opt_flow serial flow control, default none
    * \param opt_stop serial stop bits, default 1
    * \return 0 if serial device was opened successfully, 1 otherwise
    */
    bool begin(const std::string& devname, unsigned int baud_rate,
        boost::asio::serial_port_base::parity opt_parity=
            boost::asio::serial_port_base::parity(
                boost::asio::serial_port_base::parity::none),
        boost::asio::serial_port_base::character_size opt_csize=
            boost::asio::serial_port_base::character_size(8),
        boost::asio::serial_port_base::flow_control opt_flow=
            boost::asio::serial_port_base::flow_control(
                boost::asio::serial_port_base::flow_control::none),
        boost::asio::serial_port_base::stop_bits opt_stop=
            boost::asio::serial_port_base::stop_bits(
                boost::asio::serial_port_base::stop_bits::one));

    /**
     * \return true if serial device is open
     */
    bool isOpen() const;

    /**
     * \return true if error were found
     */
    bool errorStatus() const;

    /**
     * Check if there is any data in the read queue. Returns immediately.
     * \return number of characters available in the queue
     */
    size_t available();

    /**
     * Flush the buffer of incoming data asynchronously. Returns immediately.
     */
    void flush();

    /**
     * Read one byte asynchronously. Returns immediately.
     * \return next byte in the array
     */
    char read();

    /**
     * Read some data asynchronously. Returns immediately.
     * \param data array of char to be read through the serial device
     * \param size array size
     * \return number of characters actually read 0<=return<=size
     */
    size_t read(char *data, size_t size);

    /**
     * Read all available data asynchronously. Returns immediately.
     * \return the receive buffer. It iempty if no data is available
     */
    std::vector<char> readAll();

    /**
     * Read a string asynchronously. Returns immediately.
     * Can only be used if the user is sure that the serial device will not
     * send binary data. For binary data read, use read()
     * The returned string is empty if no data has arrived
     * \return a string with the received data.
     */
    std::string readString();

     /**
     * Read a line asynchronously. Returns immediately.
     * Can only be used if the user is sure that the serial device will not
     * send binary data. For binary data read, use read()
     * The returned string is empty if the line delimiter has not yet arrived.
     * \param delimiter line delimiter, default='\n'
     * \return a string with the received data. The delimiter is removed from
     * the string.
     */
    std::string readStringUntil(const std::string delim="\n");

    virtual ~SimpleSerial();

    /**
     * Close the serial device
     * \throws boost::system::system_error if any error
     */
    void end();

    /**
     * Write data asynchronously. Returns immediately.
     * \param char to be sent through the serial device
     */
    void write(const char data);

    /**
     * Write data asynchronously. Returns immediately.
     * \param data array of char to be sent through the serial device
     * \param size array size
     */
    void write(const char *data, size_t size);

     /**
     * Write data asynchronously. Returns immediately.
     * \param data to be sent through the serial device
     */
    void write(const std::vector<char>& data);

    /**
    * Write a string asynchronously. Returns immediately.
    * Can be used to send ASCII data to the serial device.
    * To send binary data, use write()
    * \param s string to send
    */
    void print(const std::string& s);

    /**
    * Write a string asynchronously with a line break. Returns immediately.
    * Can be used to send ASCII data to the serial device.
    * To send binary data, use write()
    * \param s string to send
    */
    void println(const std::string& s);

    /**
     * Read buffer maximum size
     */
    static const int readBufferSize=512;

private:
    boost::shared_ptr<SimpleSerialImpl> pimpl;

    /**
     * Callback called to start an asynchronous read operation.
     * This callback is called by the io_service in the spawned thread.
     */
    void doRead();

    /**
     * Callback called at the end of the asynchronous operation.
     * This callback is called by the io_service in the spawned thread.
     */
    void readEnd(const boost::system::error_code& error,
        size_t bytes_transferred);

    /**
     * Callback called to start an asynchronous write operation.
     * If it is already in progress, does nothing.
     * This callback is called by the io_service in the spawned thread.
     */
    void doWrite();

    /**
     * Callback called at the end of an asynchronuous write operation,
     * if there is more data to write, restarts a new write operation.
     * This callback is called by the io_service in the spawned thread.
     */
    void writeEnd(const boost::system::error_code& error);

    /**
     * Callback to close serial port
     */
    void doClose();

    /**
     * To allow derived classes to report errors
     * \param e error status
     */
    void setErrorStatus(bool e);

    /**
     * To allow derived classes to set a read callback
     */
    void setReadCallback(const
            boost::function<void (const char*, size_t)>& callback);

    /**
     * To unregister the read callback in the derived class destructor so it
     * does not get called after the derived class destructor but before the
     * base class destructor
     */
    void clearReadCallback();

    /**
     * Read callback, stores data in the buffer
     */
    void readCallback(const char *data, size_t len);

    /**
     * Finds a substring in a vector of char. Used to look for the delimiter.
     * \param v vector where to find the string
     * \param s string to find
     * \return the beginning of the place in the vector where the first
     * occurrence of the string is, or v.end() if the string was not found
     */
    static std::vector<char>::iterator findStringInVector(std::vector<char>& v,
            const std::string& s);

    std::vector<char> readQueue;
    boost::mutex readQueueMutex;
};

#endif	/* _SIMPLESERIAL_H */
