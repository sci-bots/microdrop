#include <boost/python.hpp>
#include <boost/python/suite/indexing/vector_indexing_suite.hpp>
#include "dmf_controller.h"

using namespace boost::python;

BOOST_PYTHON_MODULE(dmf_controller)
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

  class_<DmfController,boost::noncopyable>("DmfController")
    .def("Connect",&DmfController::Connect)
    .def("return_code",&DmfController::return_code)
    .def("set_debug",&DmfController::set_debug)
    .def("protocol_name",&DmfController::protocol_name)
    .def("protocol_version",&DmfController::protocol_version)
    .def("name",&DmfController::name)
    .def("version",&DmfController::version)
    .def("number_of_electrodes",&DmfController::number_of_electrodes)
    .def("state_of_all_electrodes",&DmfController::state_of_all_electrodes)
    .def("state_of_electrode",&DmfController::state_of_electrode)
    .def("sampling_rate",&DmfController::sampling_rate)
    .def("series_resistor",&DmfController::series_resistor)
    .def("set_state_of_electrode",&DmfController::set_state_of_electrode)
    .def("set_state_of_all_electrodes",&DmfController::set_state_of_all_electrodes)
    .def("set_actuation_voltage",&DmfController::set_actuation_voltage)
    .def("set_actuation_frequency",&DmfController::set_actuation_frequency)
    .def("set_sampling_rate",&DmfController::set_sampling_rate)
    .def("set_series_resistor",&DmfController::set_series_resistor)
    .def("set_pot",&DmfController::set_pot)
    .def("SampleVoltage",&DmfController::SampleVoltage)
    .def("SetExperimentLogFile",&DmfController::SetExperimentLogFile)
    .def("LogExperiment",&DmfController::SetExperimentLogFile)
    .def("MeasureImpedance",&DmfController::MeasureImpedance)
  ;
}
