<?php
/**
 * Générateur identique à numpy.random.default_rng(seed) : SeedSequence puis PCG64
 * (XSL-RR 128/64). random() = Generator.random(), choice($p) = Generator.choice(n, p=$p).
 *
 * L'état de 128 bits est gardé en 8 mots de 16 bits (poids faible d'abord) : un produit
 * de deux mots tient dans un entier PHP sans débordement. Nécessite PHP 64 bits.
 */
class Aicache_CacheusPP_Pcg64
{
    const M32 = 0xffffffff;

    /** PCG_DEFAULT_MULTIPLIER_128 = 0x2360ED051FC65DA4_4385DF649FCCF645 */
    protected static $mult = array(0xf645, 0x9fcc, 0xdf64, 0x4385, 0x5da4, 0x1fc6, 0xed05, 0x2360);

    protected $state;
    protected $inc;

    public function __construct($seed)
    {
        if (PHP_INT_SIZE < 8) {
            throw new RuntimeException('PHP 64 bits requis');
        }
        $w = self::seedSequence((int) $seed, 8);
        // generate_state(4, uint64) : u64[k] = w[2k] | w[2k+1] << 32 ; état = (u64[0] << 64) | u64[1]
        $init = self::limbs(array($w[2], $w[3], $w[0], $w[1]));
        $seq = self::limbs(array($w[6], $w[7], $w[4], $w[5]));
        $this->inc = self::shl1or1($seq);
        $this->state = array_fill(0, 8, 0);
        $this->step();
        $this->state = self::add($this->state, $init);
        $this->step();
    }

    /** Mots de 32 bits (poids faible d'abord) -> mots de 16 bits. */
    protected static function limbs(array $words)
    {
        $out = array();
        foreach ($words as $x) {
            $out[] = $x & 0xffff;
            $out[] = $x >> 16;
        }
        return $out;
    }

    protected static function mul32($a, $b)
    {
        return (((((($a >> 16) * $b) & 0xffff) << 16) + ($a & 0xffff) * $b)) & self::M32;
    }

    /** numpy.random.SeedSequence(seed).generate_state(n_words, uint32), sans spawn_key. */
    public static function seedSequence($seed, $nWords)
    {
        $entropy = array();
        do {
            $entropy[] = $seed & self::M32;
            $seed >>= 32;
        } while ($seed > 0);

        $hc = 0x43b0d7e5;
        $hashmix = function ($v) use (&$hc) {
            $v ^= $hc;
            $hc = Aicache_CacheusPP_Pcg64::mul32($hc, 0x931e8875);
            $v = Aicache_CacheusPP_Pcg64::mul32($v, $hc);
            return $v ^ ($v >> 16);
        };
        $mix = function ($x, $y) {
            $r = (Aicache_CacheusPP_Pcg64::mul32(0xca01f9dd, $x) - Aicache_CacheusPP_Pcg64::mul32(0x4973f715, $y)) & 0xffffffff;
            return $r ^ ($r >> 16);
        };
        $pool = array();
        for ($i = 0; $i < 4; $i++) {
            $pool[$i] = $hashmix(isset($entropy[$i]) ? $entropy[$i] : 0);
        }
        for ($src = 0; $src < 4; $src++) {
            for ($dst = 0; $dst < 4; $dst++) {
                if ($src !== $dst) {
                    $pool[$dst] = $mix($pool[$dst], $hashmix($pool[$src]));
                }
            }
        }
        for ($src = 4; $src < count($entropy); $src++) {
            for ($dst = 0; $dst < 4; $dst++) {
                $pool[$dst] = $mix($pool[$dst], $hashmix($entropy[$src]));
            }
        }

        $hc = 0x8b51f9dd;
        $out = array();
        for ($i = 0; $i < $nWords; $i++) {
            $v = $pool[$i % 4] ^ $hc;
            $hc = self::mul32($hc, 0x58f38ded);
            $v = self::mul32($v, $hc);
            $out[] = $v ^ ($v >> 16);
        }
        return $out;
    }

    protected static function add(array $a, array $b)
    {
        $c = 0;
        $r = array();
        for ($k = 0; $k < 8; $k++) {
            $v = $a[$k] + $b[$k] + $c;
            $r[$k] = $v & 0xffff;
            $c = $v >> 16;
        }
        return $r;
    }

    protected static function shl1or1(array $a)
    {
        $r = array();
        $c = 1;
        for ($k = 0; $k < 8; $k++) {
            $v = ($a[$k] << 1) | $c;
            $r[$k] = $v & 0xffff;
            $c = $v >> 16;
        }
        return $r;
    }

    /** state = state * MULT + inc (mod 2^128) */
    protected function step()
    {
        $a = $this->state;
        $m = self::$mult;
        $r = array();
        $c = 0;
        for ($k = 0; $k < 8; $k++) {
            $v = $c + $this->inc[$k];
            for ($i = 0; $i <= $k; $i++) {
                $v += $a[$i] * $m[$k - $i];
            }
            $r[$k] = $v & 0xffff;
            $c = $v >> 16;
        }
        $this->state = $r;
    }

    /** @return int[] sortie de 64 bits en deux mots de 32 bits : array(haut, bas) */
    public function next64()
    {
        $this->step();
        $s = $this->state;
        $lo = (($s[1] ^ $s[5]) << 16) | ($s[0] ^ $s[4]);
        $hi = (($s[3] ^ $s[7]) << 16) | ($s[2] ^ $s[6]);
        $rot = $s[7] >> 10;
        if ($rot >= 32) {
            list($hi, $lo) = array($lo, $hi);
            $rot -= 32;
        }
        if ($rot > 0) {
            list($hi, $lo) = array((($hi >> $rot) | ($lo << (32 - $rot))) & self::M32,
                                   (($lo >> $rot) | ($hi << (32 - $rot))) & self::M32);
        }
        return array($hi, $lo);
    }

    /** Generator.random() : (next64 >> 11) / 2^53 */
    public function random()
    {
        list($hi, $lo) = $this->next64();
        return (($hi << 21) | ($lo >> 11)) * (1.0 / 9007199254740992.0);
    }

    /** Generator.choice(count($p), p=$p) : cumsum, normalisation, searchsorted à droite. */
    public function choice(array $p)
    {
        $cdf = array();
        $s = 0.0;
        foreach ($p as $x) {
            $s += $x;
            $cdf[] = $s;
        }
        $u = $this->random();
        foreach ($cdf as $i => $c) {
            if ($c / $s > $u) {
                return $i;
            }
        }
        return count($cdf) - 1;
    }
}
