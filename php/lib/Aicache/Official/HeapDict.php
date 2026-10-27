<?php
/**
 * lib/heapdict.py transcrit à l'identique (mêmes échanges, même départage des égalités),
 * pour que le minimum choisi soit le même qu'en Python. Les valeurs doivent avoir lt().
 */
class Aicache_Official_HeapDict implements Countable
{
    /** clé => stdClass(key, value, index) */
    protected $htbl = array();
    protected $heap = array();

    public function has($key)
    {
        return isset($this->htbl[$key]);
    }

    public function count()
    {
        return count($this->heap);
    }

    public function min()
    {
        return $this->heap ? $this->heap[0]->value : null;
    }

    public function set($key, $value)
    {
        if (isset($this->htbl[$key])) {
            $e = $this->htbl[$key];
            $e->value = $value;
            $this->heapupify($e->index);
            $this->heapify($e->index);
        } else {
            $e = new stdClass();
            $e->key = $key;
            $e->value = $value;
            $e->index = count($this->heap);
            $this->htbl[$key] = $e;
            $this->heap[$e->index] = $e;
            $this->heapupify($e->index);
        }
    }

    public function del($key)
    {
        $e = $this->htbl[$key];
        $lastIdx = count($this->heap) - 1;
        $last = $this->heap[$lastIdx];
        $this->swap($e, $last);
        unset($this->heap[$lastIdx]);
        if ($e !== $last) {
            $this->heapupify($last->index);
            $this->heapify($last->index);
        }
        unset($this->htbl[$key]);
    }

    private function lt($a, $b)
    {
        return $a->value->lt($b->value);
    }

    private function swap($a, $b)
    {
        $t = $a->index;
        $a->index = $b->index;
        $b->index = $t;
        $this->heap[$a->index] = $a;
        $this->heap[$b->index] = $b;
    }

    private function heapupify($index)
    {
        $e = $this->heap[$index];
        while ($e->index > 0) {
            $parent = $this->heap[($e->index - 1) >> 1];
            if (!$this->lt($e, $parent)) {
                break;
            }
            $this->swap($e, $parent);
        }
    }

    private function heapify($index)
    {
        $n = count($this->heap);
        if ($index >= $n) {
            return;
        }
        $e = $this->heap[$index];
        while (true) {
            $l = 2 * $e->index + 1;
            $r = $l + 1;
            $m = $e;
            if ($l < $n && $this->lt($this->heap[$l], $m)) {
                $m = $this->heap[$l];
            }
            if ($r < $n && $this->lt($this->heap[$r], $m)) {
                $m = $this->heap[$r];
            }
            if ($m === $e) {
                break;
            }
            $this->swap($e, $m);
        }
    }
}
