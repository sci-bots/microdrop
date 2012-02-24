from nose.tools import raises

from ...utility import SetOfInts

def test_init_from_comma_separated_list():
    """
    Test initializing from a comma separated list
    """
    assert(SetOfInts("1,2,3,4").__repr__()=="SetOfInts([1, 2, 3, 4])")

def test_init_from_comma_separated_list_including_range():
    """
    Test initializing from a comma separated list including a range
    """
    assert(SetOfInts("1,2,3,4,5-7").__repr__()=="SetOfInts([1, 2, 3, 4, 5, 6, 7])")

def test_init_from_list():
    """
    Test initializing from a list
    """
    assert(SetOfInts([1,2,3,4]).__repr__()=="SetOfInts([1, 2, 3, 4])")

def test_init_from_set_of_ints():
    """
    Test initializing from another SetOfInts object
    """
    soi = SetOfInts([1,2,3,4])
    assert(SetOfInts(soi).__repr__()=="SetOfInts([1, 2, 3, 4])")

def test_string_repr():
    """
    Test __str__()
    """
    assert(str(SetOfInts("1,3,5-8"))=='1, 3, 5-8')

@raises(ValueError)
def test_invalid_input():
    """
    Test adding an invalid input (e.g., 'A')
    """
    soi = SetOfInts(['A'])

@raises(ValueError)
def test_decreasing_range():
    """
    Test adding a range that is decreasing (e.g., '10-5')
    """
    SetOfInts('10-5')
