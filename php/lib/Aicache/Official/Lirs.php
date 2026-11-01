<?php
/**
 * Portage PHP de LIRS (sylab/cacheus, code/algs/lirs.py), décision par décision : pile S,
 * HIR non résidents, file Q des HIR résidents, hirs_ratio de 1 % par défaut. Comme
 * l'original, une requête sur la même clé que la précédente ne change rien.
 */
class Aicache_Official_Lirs
{
    public $cacheSize;
    public $time = 0;
    protected $hirsRatio = 0.01;
    protected $hirsLimit;
    protected $lirsLimit;
    protected $hirsCount = 0;
    protected $lirsCount = 0;
    protected $nonresident = 0;
    protected $s;
    protected $nrHirs;
    protected $q;
    protected $lastOblock = null;

    public function __construct($cacheSize, array $kwargs = array())
    {
        $this->cacheSize = (int) $cacheSize;
        if (isset($kwargs['hirs_ratio'])) {
            $this->hirsRatio = (float) $kwargs['hirs_ratio'];
        }
        $this->hirsLimit = max(2, (int) ($this->cacheSize * $this->hirsRatio));
        $this->lirsLimit = $this->cacheSize - $this->hirsLimit;
        $this->s = new Aicache_Official_DequeDict();
        $this->nrHirs = new Aicache_Official_DequeDict();
        $this->q = new Aicache_Official_DequeDict();
    }

    public function contains($oblock)
    {
        if ($this->s->has($oblock)) {
            return $this->s->get($oblock)->inCache;
        }
        return $this->q->has($oblock);
    }

    protected function cacheFull()
    {
        return $this->lirsCount + $this->hirsCount === $this->cacheSize;
    }

    protected function hitLir($oblock)
    {
        $lruLir = $this->s->first();
        $x = $this->s->get($oblock);
        $this->s->set($oblock, $x);
        if ($lruLir === $x) {
            $this->prune();
        }
    }

    protected function prune()
    {
        while (count($this->s) > 0) {
            $x = $this->s->first();
            if ($x->isLir) {
                break;
            }
            $this->s->del($x->oblock);
            if (!$x->inCache) {
                $this->nrHirs->del($x->oblock);
                $this->nonresident--;
            }
        }
    }

    protected function hitHirInLirs($oblock)
    {
        $evicted = null;
        $x = $this->s->get($oblock);
        if ($x->inCache) {
            $this->s->del($oblock);
            $this->q->del($oblock);
            $this->hirsCount--;
        } else {
            $this->s->del($oblock);
            $this->nrHirs->del($oblock);
            $this->nonresident--;
            if ($this->cacheFull()) {
                $evicted = $this->ejectHir();
            }
        }
        if ($this->lirsCount >= $this->lirsLimit) {
            $this->ejectLir();
        }
        $this->s->set($oblock, $x);
        $x->inCache = true;
        $x->isLir = true;
        $this->lirsCount++;
        return $evicted;
    }

    protected function ejectLir()
    {
        $lru = $this->s->popFirst();
        if (!$lru->isLir) {
            throw new LogicException('LIRS : le bas de la pile S doit être un LIR');
        }
        $this->lirsCount--;
        $lru->isLir = false;
        $this->q->set($lru->oblock, $lru);
        $this->hirsCount++;
        $this->prune();
    }

    protected function ejectHir()
    {
        $lru = $this->q->popFirst();
        $this->hirsCount--;
        if ($this->s->has($lru->oblock)) {
            $this->nrHirs->set($lru->oblock, $lru);
            $lru->inCache = false;
            $this->nonresident++;
        }
        return $lru->oblock;
    }

    protected function hitHirInQ($oblock)
    {
        $x = $this->q->get($oblock);
        $this->q->set($oblock, $x);
        $this->s->set($oblock, $x);
    }

    protected function limitStack()
    {
        while (count($this->s) > 2 * $this->cacheSize) {
            $lru = $this->nrHirs->popFirst();
            $this->s->del($lru->oblock);
            $this->nonresident--;
        }
    }

    protected function miss($oblock)
    {
        $evicted = null;
        if ($this->cacheFull()) {
            $evicted = $this->ejectHir();
        }
        if ($this->lirsCount < $this->lirsLimit && $this->hirsCount === 0) {
            $this->s->set($oblock, new Aicache_Official_LirsEntry($oblock, true));
            $this->lirsCount++;
        } else {
            $x = new Aicache_Official_LirsEntry($oblock, false);
            $this->s->set($oblock, $x);
            $this->q->set($oblock, $x);
            $this->hirsCount++;
        }
        return $evicted;
    }

    /** @return array(bool hit, string|null clé évincée) */
    public function request($oblock)
    {
        $oblock = (string) $oblock;
        $hit = $this->contains($oblock);
        $evicted = null;
        $this->time++;
        if ($oblock !== $this->lastOblock) {
            $this->lastOblock = $oblock;
            if ($this->s->has($oblock)) {
                if ($this->s->get($oblock)->isLir) {
                    $this->hitLir($oblock);
                } else {
                    $evicted = $this->hitHirInLirs($oblock);
                }
            } elseif ($this->q->has($oblock)) {
                $this->hitHirInQ($oblock);
            } else {
                $evicted = $this->miss($oblock);
            }
        }
        $this->limitStack();
        return array($hit, $evicted);
    }
}
