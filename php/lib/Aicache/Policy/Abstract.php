<?php
/**
 * Base commune, équivalent de cachebench.policies.KeyedPolicy : stockage, tags et octets.
 * Une sous-classe ne fournit que ses hooks : onHit, onInsert, onRemove, victim.
 *
 * Les tableaux PHP gardent l'ordre d'insertion : c'est ce qui sert de liste chaînée.
 * Attention : PHP convertit les clés numériques ("123") en entiers ; on renvoie
 * toujours (string) $key vers l'extérieur.
 */
abstract class Aicache_Policy_Abstract implements Aicache_Policy_Interface
{
    protected $capacity;
    protected $params;
    protected $evictions = 0;
    protected $sizes = array();
    protected $tagsOf = array();
    protected $byTag = array();
    protected $used = 0;
    protected $evicted = array();

    public function __construct($capacity, array $params = array())
    {
        if ($capacity <= 0) {
            throw new InvalidArgumentException('la capacité doit être positive');
        }
        $this->capacity = (int) $capacity;
        $this->params = $params;
    }

    protected function onHit($key, Aicache_Request $req) {}
    protected function onInsert($key, Aicache_Request $req) {}
    protected function onRemove($key) {}

    /** @return string clé à évincer */
    abstract protected function victim();

    protected function admit(Aicache_Request $req)
    {
        return $req->size <= $this->capacity;
    }

    public function access(Aicache_Request $req)
    {
        $key = $req->key;
        if (isset($this->sizes[$key])) {
            if ($this->sizes[$key] !== $req->size) {
                $this->remove($key);   // nouvelle version de la page
            } else {
                $this->onHit($key, $req);
                return true;
            }
        }
        if (!$this->admit($req)) {
            return false;
        }
        while ($this->used + $req->size > $this->capacity) {
            $v = (string) $this->victim();
            $this->remove($v);
            $this->evicted[] = $v;
            $this->evictions++;
        }
        $this->sizes[$key] = $req->size;
        $this->tagsOf[$key] = $req->tags;
        foreach ($req->tags as $t) {
            $this->byTag[$t][$key] = true;
        }
        $this->used += $req->size;
        $this->onInsert($key, $req);
        return false;
    }

    public function invalidate(array $tags)
    {
        $keys = array();
        foreach ($tags as $t) {
            if (isset($this->byTag[$t])) {
                foreach ($this->byTag[$t] as $k => $_) {
                    $keys[(string) $k] = true;
                }
            }
        }
        foreach ($keys as $k => $_) {
            $this->remove((string) $k);
        }
        return count($keys);
    }

    protected function remove($key)
    {
        $this->used -= $this->sizes[$key];
        unset($this->sizes[$key]);
        foreach ($this->tagsOf[$key] as $t) {
            unset($this->byTag[$t][$key]);
            if (empty($this->byTag[$t])) {
                unset($this->byTag[$t]);
            }
        }
        unset($this->tagsOf[$key]);
        $this->onRemove($key);
    }

    public function usedBytes()
    {
        return $this->used;
    }

    public function contains($key)
    {
        return isset($this->sizes[$key]);
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
