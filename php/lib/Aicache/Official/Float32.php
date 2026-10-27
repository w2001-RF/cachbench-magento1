<?php
/** Arrondi en float32 (numpy.float32) : PHP ne calcule qu'en double. */
class Aicache_Official_Float32
{
    public static function f($x)
    {
        $u = unpack('f', pack('f', $x));
        return $u[1];
    }

    /** round(x, 3) de Python sur un float : arrondi décimal exact, moitié au pair. */
    public static function pyRound3($x)
    {
        return (float) sprintf('%.3F', $x);
    }

    /** round(x, 3) sur un numpy.float64 : rint(x * 1000) / 1000. */
    public static function npRound3($x)
    {
        $y = $x * 1000.0;
        $f = floor($y);
        $d = $y - $f;
        if ($d > 0.5 || ($d == 0.5 && fmod($f, 2.0) != 0.0)) {
            $f += 1.0;
        }
        return $f / 1000.0;
    }
}
