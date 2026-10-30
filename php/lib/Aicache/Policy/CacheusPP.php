<?php
/**
 * CACHEUS++, comme cachebench.policies.cacheus_pp : get, puis en cas de miss shouldCache
 * et put, dans l'ordre du runner de cache_benchmark.
 *
 * La route Magento (kind) sert de catégorie et cost_ms de coût de miss pour GDSF (sans coût,
 * tier_costs ou 1.0). Octets ou unités. Un objet de plus de max_object_fraction (10 %) de la
 * capacité n'est jamais admis : dans Magento, la capacité doit dépasser dix fois la plus
 * grosse entrée (la configuration fait plusieurs Mo).
 *
 * Une purge ou une page qui change de taille retire l'entrée sans que l'algorithme l'ait
 * choisi : ni historique fantôme ni apprentissage.
 */
class Aicache_Policy_CacheusPP implements Aicache_Policy_Interface
{
    /** @var Aicache_CacheusPP_Algorithm */
    protected $alg;
    protected $capacity;
    protected $byTag = array();
    protected $tagsOf = array();   // tags de chaque clé résidente, pour la retirer de byTag à l'éviction
    protected $evictions = 0;
    protected $evicted = array();

    public function __construct($capacity, array $params = array())
    {
        if ($capacity <= 0) {
            throw new InvalidArgumentException('la capacité doit être positive');
        }
        $this->capacity = (int) $capacity;
        $this->alg = new Aicache_CacheusPP_Algorithm($this->capacity, $params);
    }

    public function access(Aicache_Request $req)
    {
        $key = $req->key;
        if (isset($this->alg->cache[$key]) && $this->alg->cache[$key] !== $req->size) {
            $this->drop($key);   // nouvelle version de la page
        }
        $cost = $req->costMs > 0 ? $req->costMs : null;
        if ($this->alg->get($key, $req->size, $req->kind, $cost)) {
            return true;
        }
        if ($this->alg->shouldCache($key, $req->size, $req->kind, $cost)) {
            $ev = $this->alg->put($key, $req->size, $req->kind, $cost);
            $this->evictions += count($ev);
            foreach ($ev as $k) {
                $this->evicted[] = $k;
                $this->untag($k);
            }
            if (isset($this->alg->cache[$key])) {
                $this->tagsOf[$key] = $req->tags;
                foreach ($req->tags as $t) {
                    $this->byTag[$t][$key] = true;
                }
            }
        }
        return false;
    }

    protected function drop($key)
    {
        $this->alg->drop($key);
        $this->untag($key);
    }

    protected function untag($key)
    {
        if (!isset($this->tagsOf[$key])) {
            return;
        }
        foreach ($this->tagsOf[$key] as $t) {
            unset($this->byTag[$t][$key]);
            if (empty($this->byTag[$t])) {
                unset($this->byTag[$t]);
            }
        }
        unset($this->tagsOf[$key]);
    }

    public function invalidate(array $tags)
    {
        $keys = array();
        foreach ($tags as $t) {
            if (isset($this->byTag[$t])) {
                $keys += $this->byTag[$t];
                unset($this->byTag[$t]);
            }
        }
        $n = 0;
        foreach ($keys as $k => $_) {
            if (isset($this->alg->cache[$k])) {
                $this->drop($k);
                $n++;
            }
        }
        return $n;
    }

    public function usedBytes()
    {
        return $this->alg->currentSize;
    }

    public function contains($key)
    {
        return isset($this->alg->cache[$key]);
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

    public function stats()
    {
        return $this->alg->stats();
    }
}
