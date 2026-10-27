<?php
/**
 * Portage PHP de CACHEUS (sylab/cacheus, code/algs/cacheus.py), décision par décision.
 *
 * Le type numpy du taux d'apprentissage change le calcul des poids, on le suit donc :
 * un numpy.float64 (« fort ») fait passer les poids en float64, un float Python (« faible »)
 * les laisse en float32. Idem pour round(), qui n'arrondit pas pareil selon le type.
 * Un taux est stocké comme array(valeur, fort).
 */
class Aicache_Official_Cacheus
{
    public $cacheSize;
    public $time = 0;
    protected $s;
    protected $q;
    protected $lfu;
    protected $lruHist;
    protected $lfuHist;
    protected $historySize;
    public $W;
    protected $W64 = false;
    protected $qLimit;
    protected $sLimit;
    protected $qSize = 0;
    protected $sSize = 0;
    protected $demCount = 0;
    protected $norCount = 0;
    protected $rng;

    // Taux d'apprentissage adaptatif (Cacheus_Learning_Rate)
    public $lr;
    protected $lrReset;
    protected $lrCurr;
    protected $lrPrev;
    protected $period;
    public $hitrate = 0;
    protected $hitratePrev = 0.0;
    protected $hitrateZeroCount = 0;
    protected $hitrateNegaCount = 0;

    public function __construct($cacheSize, array $kwargs = array())
    {
        $this->rng = new Aicache_Official_Mt19937(123);
        $this->cacheSize = (int) $cacheSize;
        $this->s = new Aicache_Official_DequeDict();
        $this->q = new Aicache_Official_DequeDict();
        $this->lfu = new Aicache_Official_HeapDict();
        $this->historySize = intdiv($this->cacheSize, 2);
        $this->lruHist = new Aicache_Official_DequeDict();
        $this->lfuHist = new Aicache_Official_DequeDict();

        $this->period = $this->cacheSize;
        $this->lr = array(sqrt((2.0 * log(2)) / $this->period), true);
        if (isset($kwargs['learning_rate'])) {
            $this->lr = array((float) $kwargs['learning_rate'], false);
        }
        $this->lrReset = self::pmin(self::pmax($this->lr, array(0.001, false)), array(1.0, false));
        $this->lrCurr = $this->lr;
        $this->lrPrev = array(0.0, false);

        $initial = isset($kwargs['initial_weight']) ? (float) $kwargs['initial_weight'] : 0.5;
        if (isset($kwargs['history_size'])) {
            $this->historySize = (int) $kwargs['history_size'];
        }
        $this->W = array(Aicache_Official_Float32::f($initial), Aicache_Official_Float32::f(1 - $initial));
        $this->qLimit = max(1, (int) ((0.01 * $this->cacheSize) + 0.5));
        $this->sLimit = $this->cacheSize - $this->qLimit;
    }

    /** min(a, b) de Python : renvoie a sauf si b < a. */
    private static function pmin($a, $b)
    {
        return $b[0] < $a[0] ? $b : $a;
    }

    private static function pmax($a, $b)
    {
        return $b[0] > $a[0] ? $b : $a;
    }

    private static function round3($x)
    {
        return array($x[1] ? Aicache_Official_Float32::npRound3($x[0]) : Aicache_Official_Float32::pyRound3($x[0]), $x[1]);
    }

    protected function updateLearningRate($time)
    {
        if ($time % $this->period === 0) {
            $hitrateCurr = Aicache_Official_Float32::pyRound3($this->hitrate / (float) $this->period);
            $hitrateDiff = Aicache_Official_Float32::pyRound3($hitrateCurr - $this->hitratePrev);
            $c = self::round3($this->lrCurr);
            $p = self::round3($this->lrPrev);
            $dLR = array($c[0] - $p[0], $c[1] || $p[1]);
            $d = $dLR[0] * $hitrateDiff;
            $delta = $d > 0 ? 1 : ($d < 0 ? -1 : 0);
            $lr = $this->lr;
            $strong = $lr[1] || $dLR[1];
            if ($delta > 0) {
                $this->lr = self::pmin(array($lr[0] + abs($lr[0] * $dLR[0]), $strong), array(1.0, false));
                $this->hitrateNegaCount = 0;
                $this->hitrateZeroCount = 0;
            } elseif ($delta < 0) {
                $this->lr = self::pmax(array($lr[0] - abs($lr[0] * $dLR[0]), $strong), array(0.001, false));
                $this->hitrateNegaCount = 0;
                $this->hitrateZeroCount = 0;
            } elseif ($hitrateDiff <= 0) {
                if ($hitrateCurr <= 0 && $hitrateDiff == 0) {
                    $this->hitrateZeroCount++;
                }
                if ($hitrateDiff < 0) {
                    $this->hitrateNegaCount++;
                    $this->hitrateZeroCount++;
                }
                if ($this->hitrateZeroCount >= 10) {
                    $this->lr = $this->lrReset;
                    $this->hitrateZeroCount = 0;
                } elseif ($hitrateDiff < 0) {
                    if ($this->hitrateNegaCount >= 10) {
                        $this->lr = $this->lrReset;
                        $this->hitrateNegaCount = 0;
                    } else {
                        $this->updateInRandomDirection();
                    }
                }
            }
            $this->lrPrev = $this->lrCurr;
            $this->lrCurr = $this->lr;
            $this->hitratePrev = $hitrateCurr;
            $this->hitrate = 0;
        }
    }

    protected function updateInRandomDirection()
    {
        $lr = $this->lr;
        if ($lr[0] >= 1) {
            $this->lr = array(0.9, false);
        } elseif ($lr[0] <= 0.001) {
            $this->lr = array(0.005, false);
        } elseif ($this->rng->choice2() === 0) {
            $this->lr = self::pmin(array($lr[0] * 1.25, $lr[1]), array(1.0, false));
        } else {
            $this->lr = self::pmax(array($lr[0] * 0.75, $lr[1]), array(0.001, false));
        }
    }

    public function contains($oblock)
    {
        return $this->s->has($oblock) || $this->q->has($oblock);
    }

    protected function hitInS($oblock)
    {
        $x = $this->s->get($oblock);
        $x->time = $this->time;
        $this->s->set($oblock, $x);
        $x->freq++;
        $this->lfu->set($oblock, $x);
    }

    protected function hitInQ($oblock)
    {
        $x = $this->q->get($oblock);
        $x->time = $this->time;
        $x->freq++;
        $this->lfu->set($oblock, $x);
        if ($x->isDemoted) {
            $this->adjustSize(true);
            $x->isDemoted = false;
            $this->demCount--;
        }
        $this->q->del($x->oblock);
        $this->qSize--;
        if ($this->sSize >= $this->sLimit) {
            $y = $this->s->popFirst();
            $y->isDemoted = true;
            $this->demCount++;
            $this->sSize--;
            $this->q->set($y->oblock, $y);
            $this->qSize++;
        }
        $this->s->set($x->oblock, $x);
        $this->sSize++;
    }

    protected function addToS($oblock, $freq, $isNew)
    {
        $x = new Aicache_Official_Entry($oblock, $freq, $this->time, true, $isNew);
        $this->s->set($oblock, $x);
        $this->lfu->set($oblock, $x);
        $this->sSize++;
    }

    protected function addToQ($oblock, $freq, $isNew)
    {
        $x = new Aicache_Official_Entry($oblock, $freq, $this->time, true, $isNew);
        $this->q->set($oblock, $x);
        $this->lfu->set($oblock, $x);
        $this->qSize++;
    }

    protected function addToHistory($x, $policy)
    {
        if ($policy === -1) {
            return;
        }
        if ($policy === 0) {
            $h = $this->lruHist;
            if ($x->isNew) {
                $this->norCount++;
            }
        } else {
            $h = $this->lfuHist;
        }
        if (count($h) === $this->historySize) {
            $old = $h->first();
            $h->del($old->oblock);
            if ($h === $this->lruHist && $old->isNew) {
                $this->norCount--;
            }
        }
        $h->set($x->oblock, $x);
    }

    protected function getChoice()
    {
        $r = $this->rng->rand();
        if (!$this->W64) {
            $r = Aicache_Official_Float32::f($r);   // comparaison float Python / float32 faite en float32
        }
        return $r < $this->W[0] ? 0 : 1;
    }

    protected function evict()
    {
        $lru = $this->q->first();
        $lfu = $this->lfu->min();
        $policy = $this->getChoice();
        if ($lru === $lfu) {
            $evicted = $lru;
            $policy = -1;
        } elseif ($policy === 0) {
            $evicted = $lru;
            $this->q->del($evicted->oblock);
            $this->qSize--;
        } else {
            $evicted = $lfu;
            if ($this->s->has($evicted->oblock)) {
                $this->s->del($evicted->oblock);
                $this->sSize--;
            } elseif ($this->q->has($evicted->oblock)) {
                $this->q->del($evicted->oblock);
                $this->qSize--;
            }
        }
        if ($evicted->isDemoted) {
            $this->demCount--;
            $evicted->isDemoted = false;
        }
        if ($policy === -1) {
            $this->q->del($evicted->oblock);
            $this->qSize--;
        }
        $this->lfu->del($evicted->oblock);
        $evicted->evictedTime = $this->time;
        $this->addToHistory($evicted, $policy);
        return $evicted->oblock;
    }

    protected function adjustWeights($rLru, $rLfu)
    {
        $F = 'Aicache_Official_Float32';
        $r = array($F::f($rLru), $F::f($rLfu));
        if ($this->lr[1]) {
            // float64 * tableau float32 -> float64
            $e = array(exp($this->lr[0] * $r[0]), exp($this->lr[0] * $r[1]));
            $wide = true;
        } else {
            $l = $F::f($this->lr[0]);
            $e = array($F::f(exp($F::f($l * $r[0]))), $F::f(exp($F::f($l * $r[1]))));
            $wide = $this->W64;
        }
        $w0 = $this->W[0] * $e[0];
        $w1 = $this->W[1] * $e[1];
        if ($wide) {
            $s = $w0 + $w1;
            $this->W = array($w0 / $s, $w1 / $s);
        } else {
            $w0 = $F::f($w0);
            $w1 = $F::f($w1);
            $s = $F::f($w0 + $w1);
            $this->W = array($F::f($w0 / $s), $F::f($w1 / $s));
        }
        $this->W64 = $wide;
        $c = $wide ? 0.99 : $F::f(0.99);
        if ($this->W[0] >= $c) {
            $this->W = array($F::f(0.99), $F::f(0.01));
            $this->W64 = false;
        } elseif ($this->W[1] >= $c) {
            $this->W = array($F::f(0.01), $F::f(0.99));
            $this->W64 = false;
        }
    }

    protected function adjustSize($hitInQ)
    {
        if ($hitInQ) {
            $dem = max(1, $this->demCount);
            $this->sLimit = min($this->cacheSize - 1, $this->sLimit + max(1, (int) (($this->norCount / $dem) + 0.5)));
            $this->qLimit = $this->cacheSize - $this->sLimit;
        } else {
            $nor = max(1, $this->norCount);
            $this->qLimit = min($this->cacheSize - 1, $this->qLimit + max(1, (int) (($this->demCount / $nor) + 0.5)));
            $this->sLimit = $this->cacheSize - $this->qLimit;
        }
    }

    protected function hitInHist($oblock, $isLru)
    {
        $evicted = null;
        $h = $isLru ? $this->lruHist : $this->lfuHist;
        $e = $h->get($oblock);
        $h->del($oblock);
        if ($isLru) {
            if ($e->isNew) {
                $this->norCount--;
                $e->isNew = false;
                $this->adjustSize(false);
            }
            $this->adjustWeights(-1, 0);
        } else {
            $this->adjustWeights(0, -1);
        }
        if ($this->sSize + $this->qSize >= $this->cacheSize) {
            $evicted = $this->evict();
        }
        $this->addToS($e->oblock, $e->freq, false);   // le code officiel reprend entry.freq tel quel
        $this->limitStack();
        return $evicted;
    }

    protected function limitStack()
    {
        while ($this->sSize >= $this->sLimit) {
            $d = $this->s->popFirst();
            $this->sSize--;
            $d->isDemoted = true;
            $this->demCount++;
            $this->q->set($d->oblock, $d);
            $this->qSize++;
        }
    }

    protected function miss($oblock)
    {
        $evicted = null;
        if ($this->sSize < $this->sLimit && $this->qSize === 0) {
            $this->addToS($oblock, 1, false);
        } elseif ($this->sSize + $this->qSize < $this->cacheSize && $this->qSize < $this->qLimit) {
            $this->addToQ($oblock, 1, false);
        } else {
            if ($this->sSize + $this->qSize >= $this->cacheSize) {
                $evicted = $this->evict();
            }
            $this->addToQ($oblock, 1, true);
            $this->limitStack();
        }
        return $evicted;
    }

    /** @return array(bool hit, string|null clé évincée) */
    public function request($oblock)
    {
        $this->time++;
        $this->updateLearningRate($this->time);
        $evicted = null;
        $miss = true;
        if ($this->s->has($oblock)) {
            $this->hitInS($oblock);
            $miss = false;
        } elseif ($this->q->has($oblock)) {
            $this->hitInQ($oblock);
            $miss = false;
        } elseif ($this->lruHist->has($oblock)) {
            $evicted = $this->hitInHist($oblock, true);
        } elseif ($this->lfuHist->has($oblock)) {
            $evicted = $this->hitInHist($oblock, false);
        } else {
            $evicted = $this->miss($oblock);
        }
        if (!$miss) {
            $this->hitrate++;
        }
        return array(!$miss, $evicted);
    }
}
