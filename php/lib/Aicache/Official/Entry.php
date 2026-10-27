<?php
/** Entrée de page de LeCaR et CACHEUS. */
class Aicache_Official_Entry
{
    public $oblock;
    public $freq;
    public $time;
    public $evictedTime;
    public $isDemoted = false;
    public $isNew = true;
    /** true : départage CACHEUS (le plus récent d'abord) ; false : LeCaR (ordre des clés) */
    public $byTime;

    public function __construct($oblock, $freq, $time, $byTime, $isNew = true)
    {
        $this->oblock = (string) $oblock;
        $this->freq = $freq;
        $this->time = $time;
        $this->byTime = $byTime;
        $this->isNew = $isNew;
    }

    public function lt(Aicache_Official_Entry $o)
    {
        if ($this->freq === $o->freq) {
            return $this->byTime ? $this->time > $o->time : strcmp($this->oblock, $o->oblock) < 0;
        }
        return $this->freq < $o->freq;
    }
}
