<?php
declare(strict_types=1);
if (array_sum([2, 3, 5]) !== 10) {
    throw new RuntimeException("PHP smoke assertion failed");
}
echo "ZEIBAEL_PHP_OK\n";
