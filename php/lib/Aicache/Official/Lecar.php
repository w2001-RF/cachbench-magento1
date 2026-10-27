<?php
/**
 * Portage PHP de LeCaR (sylab/cacheus, code/algs/lecar.py), décision par décision :
 * même générateur aléatoire (graine 123), mêmes structures, poids en float32 comme numpy.
 * Seule différence connue : numpy calcule exp() en float32 avec sa propre routine, qui
 * diffère parfois d'un ulp ; les poids peuvent donc s'écarter très légèrement.
 */
class Aicache_Official_Lecar
{
    public $cacheSize;
    public $time = 0;
    protected $lru;
    protected $lfu;
    protected $lruHist;
    protected $lfuHist;
    protected $historySize;
    protected $learningRate = 0.45;
    protected $discountRate;
    public $W;
    protected $rng;

    public function __construct($cacheSize, array $kwargs = array())
    {
        $this->rng = new Aicache_Official_Mt19937(123);
        $this->cacheSize = (int) $cacheSize;
        $this->lru = new Aicache_Official_DequeDict();
        $this->lfu = new Aicache_Official_HeapDict();
        $this->historySize = intdiv($this->cacheSize, 2);
        $this->lruHist = new Aicache_Official_DequeDict();
        $this->lfuHist = new Aicache_Official_DequeDict();
        $initial = 0.5;
        $this->discountRate = pow(0.005, 1.0 / $this->cacheSize);
        if (isset($kwargs['learning_rate'])) {
            $this->learningRate = (float) $kwargs['learning_rate'];
        }
        if (isset($kwargs['initial_weight'])) {
            $initial = (float) $kwargs['initial_weight'];
        }
        if (isset($kwargs['history_size'])) {
            $this->historySize = (int) $kwargs['history_size'];
        }
        $this->W = array(Aicache_Official_Float32::f($initial), Aicache_Official_Float32::f(1 - $initial));
    }

    public function contains($oblock)
    {
        return $this->lru->has($oblock);
    }

    protected function addToCache($oblock, $freq)
    {
        $x = new Aicache_Official_Entry($oblock, $freq, $this->time, false);
        $this->lru->set($oblock, $x);
        $this->lfu->set($oblock, $x);
    }

    protected function addToHistory($x, $policy)
    {
        if ($policy === -1) {
            return;
        }
        $h = $policy === 0 ? $this->lruHist : $this->lfuHist;
        if (count($h) === $this->historySize) {
            $h->del($h->first()->oblock);
        }
        $h->set($x->oblock, $x);
    }

    protected function getChoice()
    {
        // numpy compare un float Python à un float32 en float32
        return Aicache_Official_Float32::f($this->rng->rand()) < $this->W[0] ? 0 : 1;
    }

    protected function evict()
    {
        $lru = $this->lru->first();
        $lfu = $this->lfu->min();
        $policy = $this->getChoice();
        if ($lru === $lfu) {
            $evicted = $lru;
            $policy = -1;
        } elseif ($policy === 0) {
            $evicted = $lru;
        } else {
            $evicted = $lfu;
        }
        $this->lru->del($evicted->oblock);
        $this->lfu->del($evicted->oblock);
        $evicted->evictedTime = $this->time;
        $this->addToHistory($evicted, $policy);
        return $evicted->oblock;
    }

    protected function hit($oblock)
    {
        $x = $this->lru->get($oblock);
        $x->time = $this->time;
        $this->lru->set($oblock, $x);
        $x->freq++;
        $this->lfu->set($oblock, $x);
    }

    protected function adjustWeights($rLru, $rLfu)
    {
        $F = 'Aicache_Official_Float32';
        $lr = $F::f($this->learningRate);
        $w0 = $F::f($this->W[0] * $F::f(exp($F::f($lr * $F::f($rLru)))));
        $w1 = $F::f($this->W[1] * $F::f(exp($F::f($lr * $F::f($rLfu)))));
        $s = $F::f($w0 + $w1);
        $this->W = array($F::f($w0 / $s), $F::f($w1 / $s));
        if ($this->W[0] >= $F::f(0.99)) {
            $this->W = array($F::f(0.99), $F::f(0.01));
        } elseif ($this->W[1] >= $F::f(0.99)) {
            $this->W = array($F::f(0.01), $F::f(0.99));
        }
    }

    protected function miss($oblock)
    {
        $evicted = null;
        $freq = 1;
        if ($this->lruHist->has($oblock)) {
            $e = $this->lruHist->get($oblock);
            $freq = $e->freq + 1;
            $this->lruHist->del($oblock);
            $this->adjustWeights(-pow($this->discountRate, $this->time - $e->evictedTime), 0);
        } elseif ($this->lfuHist->has($oblock)) {
            $e = $this->lfuHist->get($oblock);
            $freq = $e->freq + 1;
            $this->lfuHist->del($oblock);
            $this->adjustWeights(0, -pow($this->discountRate, $this->time - $e->evictedTime));
        }
        if (count($this->lru) === $this->cacheSize) {
            $evicted = $this->evict();
        }
        $this->addToCache($oblock, $freq);
        return $evicted;
    }

    /** @return array(bool hit, string|null clé évincée) */
    public function request($oblock)
    {
        $this->time++;
        if ($this->contains($oblock)) {
            $this->hit($oblock);
            return array(true, null);
        }
        return array(false, $this->miss($oblock));
    }
}
