<?php
/** lib/dequedict.py : dictionnaire ordonné, une mise à jour replace l'élément en fin. */
class Aicache_Official_DequeDict implements Countable
{
    protected $items = array();

    public function has($key)
    {
        return isset($this->items[$key]);
    }

    public function get($key)
    {
        return $this->items[$key];
    }

    public function set($key, $value)
    {
        unset($this->items[$key]);
        $this->items[$key] = $value;
    }

    public function del($key)
    {
        unset($this->items[$key]);
    }

    public function first()
    {
        foreach ($this->items as $v) {
            return $v;
        }
        return null;
    }

    public function popFirst()
    {
        foreach ($this->items as $k => $v) {
            unset($this->items[$k]);
            return $v;
        }
        return null;
    }

    public function count()
    {
        return count($this->items);
    }
}
