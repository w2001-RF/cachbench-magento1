<?php
/**
 * Adaptateur des portages LeCaR / CACHEUS / ARC / LIRS, comme cachebench.policies.official :
 * ces algorithmes comptent des objets (taille 1) et ne savent pas retirer une entrée,
 * donc une purge rend l'entrée périmée : la requête suivante sur la clé est un miss.
 */
class Aicache_Policy_Official implements Aicache_Policy_Interface
{
    protected $alg;
    protected $capacity;
    protected $resident = array();
    protected $stale = array();
    protected $byTag = array();
    protected $evictions = 0;
    protected $evicted = array();

    /** @param string $name lecar, cacheus, arc ou lirs */
    public function __construct($name, $capacity, array $params = array())
    {
        $this->capacity = (int) $capacity;
        unset($params['seed'], $params['window_size']);
        if ($name === 'lecar') {
            $this->alg = new Aicache_Official_Lecar($this->capacity, $params);
        } elseif ($name === 'cacheus') {
            $this->alg = new Aicache_Official_Cacheus($this->capacity, $params);
        } elseif ($name === 'arc') {
            $this->alg = new Aicache_Official_Arc($this->capacity, $params);
        } elseif ($name === 'lirs') {
            $this->alg = new Aicache_Official_Lirs($this->capacity, $params);
        } else {
            throw new InvalidArgumentException("algorithme officiel non porté : $name");
        }
    }

    public function access(Aicache_Request $req)
    {
        if ($req->size !== 1) {
            throw new InvalidArgumentException('lecar, cacheus, arc et lirs comptent des objets : utiliser des tailles unitaires');
        }
        $key = $req->key;
        list($hit, $ev) = $this->alg->request($key);
        if ($ev !== null) {
            unset($this->resident[$ev], $this->stale[$ev]);
            $this->evicted[] = (string) $ev;
            $this->evictions++;
        }
        if ($this->alg->contains($key)) {
            $this->resident[$key] = true;
            foreach ($req->tags as $t) {
                $this->byTag[$t][$key] = true;
            }
        }
        $hit = $hit && !isset($this->stale[$key]);
        unset($this->stale[$key]);
        return $hit;
    }

    public function invalidate(array $tags)
    {
        $n = 0;
        foreach ($tags as $t) {
            if (!isset($this->byTag[$t])) {
                continue;
            }
            foreach ($this->byTag[$t] as $k => $_) {
                if (isset($this->resident[$k])) {
                    $this->stale[$k] = true;
                    $n++;
                }
            }
            unset($this->byTag[$t]);
        }
        return $n;
    }

    public function usedBytes()
    {
        return count($this->resident);
    }

    public function contains($key)
    {
        return isset($this->resident[$key]) && !isset($this->stale[$key]);
    }

    public function getCapacity()
    {
        return $this->capacity;
    }

    public function getEvictions()
    {
        return $this->evictions;
    }

    public function popEvicted()
    {
        $e = $this->evicted;
        $this->evicted = array();
        return $e;
    }
}
