#include <boost/python.hpp>
#include <boost/python/suite/indexing/vector_indexing_suite.hpp>
#include "dmf_control_board.h"

using namespace boost::python;

const uint8_t RemoteObject::RETURN_OK;
const uint8_t RemoteObject::RETURN_GENERAL_ERROR;
const uint8_t RemoteObject::RETURN_UNKNOWN_COMMAND;
const uint8_t RemoteObject::RETURN_TIMEOUT;
const uint8_t RemoteObject::RETURN_NOT_CONNECTED;
const uint8_t RemoteObject::RETURN_BAD_INDEX;
const uint8_t RemoteObject::RETURN_BAD_PACKET_SIZE;
const uint8_t RemoteObject::RETURN_BAD_CRC;

BOOST_PYTHON_MODULE(dmf_control_board_base)
{
  class_<std::vector<uint8_t> >("uint8_tVector")
    .def(vector_indexing_suite<std::vector<uint8_t> >())
  ;

  class_<std::vector<uint16_t> >("uint16_tVector")
    .def(vector_indexing_suite<std::vector<uint16_t> >())
  ;

  class_<std::vector<float> >("floatVector")
    .def(vector_indexing_suite<std::vector<float> >())
  ;

object DmfControlBoard_class
  = class_<DmfControlBoard,boost::noncopyable>("DmfControlBoard")
    .def("Connect",&DmfControlBoard::Connect)
    .def("connected",&DmfControlBoard::connected)
    .def("return_code",&DmfControlBoard::return_code)
    .def("set_debug",&DmfControlBoard::set_debug)
    .def("protocol_name",&DmfControlBoard::protocol_name)
    .def("protocol_version",&DmfControlBoard::protocol_version)
    .def("name",&DmfControlBoard::name)
    .def("manufacturer",&DmfControlBoard::manufacturer)
    .def("software_version",&DmfControlBoard::software_version)
    .def("hardware_version",&DmfControlBoard::hardware_version)
    .def("url",&DmfControlBoard::url)
    .def("number_of_channels",&DmfControlBoard::number_of_channels)
    .def("state_of_all_channels",&DmfControlBoard::state_of_all_channels)
    .def("state_of_channel",&DmfControlBoard::state_of_channel)
    .def("sampling_rate",&DmfControlBoard::sampling_rate)
    .def("series_resistor",&DmfControlBoard::series_resistor)
    .def("set_state_of_channel",&DmfControlBoard::set_state_of_channel)
    .def("set_state_of_all_channels",&DmfControlBoard::set_state_of_all_channels)
    .def("set_actuation_voltage",&DmfControlBoard::set_actuation_voltage)
    .def("set_actuation_frequency",&DmfControlBoard::set_actuation_frequency)
    .def("set_sampling_rate",&DmfControlBoard::set_sampling_rate)
    .def("set_series_resistor",&DmfControlBoard::set_series_resistor)
    .def("set_pot",&DmfControlBoard::set_pot)
    .def("SampleVoltage",&DmfControlBoard::SampleVoltage)
    .def("SetExperimentLogFile",&DmfControlBoard::SetExperimentLogFile)
    .def("LogExperiment",&DmfControlBoard::SetExperimentLogFile)
    .def("MeasureImpedance",&DmfControlBoard::MeasureImpedance)
  ;
DmfControlBoard_class.attr("RETURN_OK") = DmfControlBoard::RETURN_OK;
DmfControlBoard_class.attr("RETURN_GENERAL_ERROR") = DmfControlBoard::RETURN_GENERAL_ERROR;
DmfControlBoard_class.attr("RETURN_UNKNOWN_COMMAND") = DmfControlBoard::RETURN_UNKNOWN_COMMAND;
DmfControlBoard_class.attr("RETURN_TIMEOUT") = DmfControlBoard::RETURN_TIMEOUT;
DmfControlBoard_class.attr("RETURN_NOT_CONNECTED") = DmfControlBoard::RETURN_NOT_CONNECTED;
DmfControlBoard_class.attr("RETURN_BAD_INDEX") = DmfControlBoard::RETURN_BAD_INDEX;
DmfControlBoard_class.attr("RETURN_BAD_PACKET_SIZE") = DmfControlBoard::RETURN_BAD_PACKET_SIZE;
DmfControlBoard_class.attr("RETURN_BAD_CRC") = DmfControlBoard::RETURN_BAD_CRC;
}
