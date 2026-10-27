<?php
/**
 * Mersenne Twister identique à numpy.random (RandomState « legacy ») :
 * seed(n) = init_genrand(n), rand() = random_sample(), choice de 2 éléments = next32 & 1.
 * Nécessite PHP 64 bits.
 */
class Aicache_Official_Mt19937
{
    const N = 624;
    const M = 397;

    protected $mt = array();
    protected $i = 625;

    public function __construct($seed)
    {
        if (PHP_INT_SIZE < 8) {
            throw new RuntimeException('PHP 64 bits requis');
        }
        $this->mt[0] = $seed & 0xffffffff;
        for ($i = 1; $i < self::N; $i++) {
            $p = $this->mt[$i - 1];
            $this->mt[$i] = (1812433253 * ($p ^ ($p >> 30)) + $i) & 0xffffffff;
        }
        $this->i = self::N;
    }

    protected function reload()
    {
        $mt = $this->mt;
        for ($k = 0; $k < self::N; $k++) {
            $y = ($mt[$k] & 0x80000000) | ($mt[($k + 1) % self::N] & 0x7fffffff);
            $mt[$k] = $mt[($k + self::M) % self::N] ^ ($y >> 1) ^ (($y & 1) ? 0x9908b0df : 0);
        }
        $this->mt = $mt;
        $this->i = 0;
    }

    public function next32()
    {
        if ($this->i >= self::N) {
            $this->reload();
        }
        $y = $this->mt[$this->i++];
        $y ^= $y >> 11;
        $y ^= ($y << 7) & 0x9d2c5680;
        $y ^= ($y << 15) & 0xefc60000;
        $y ^= $y >> 18;
        return $y & 0xffffffff;
    }

    public function rand()
    {
        $a = $this->next32() >> 5;
        $b = $this->next32() >> 6;
        return ($a * 67108864.0 + $b) / 9007199254740992.0;
    }

    /** np.random.choice sur 2 éléments : index tiré. */
    public function choice2()
    {
        return $this->next32() & 1;
    }
}
