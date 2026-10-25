program zeibael
    implicit none
    integer :: total
    total = 2 + 3 + 5
    if (total /= 10) error stop "Fortran smoke assertion failed"
    print '(A)', "ZEIBAEL_FORTRAN_OK"
end program zeibael
