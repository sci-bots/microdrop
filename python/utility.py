def is_float(s):
    try: return (float(s), True)[1]
    except (ValueError, TypeError), e: return False

def is_int(s):
    try: return (int(s), True)[1]
    except (ValueError, TypeError), e: return False