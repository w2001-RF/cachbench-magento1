<?php
/** _Entry de cacheus_pp.py : une entrée résidente. */
class Aicache_CacheusPP_Entry
{
    public $size;
    public $category;
    public $cost;
    public $freq;
    public $lastAccess;
    public $version = 0;
    public $hits = 0;
    public $labeled = false;
    /** @var float[]|null */
    public $admitFeatures;

    public function __construct($size, $category, $cost, $freq, $lastAccess, $admitFeatures)
    {
        $this->size = $size;
        $this->category = $category;
        $this->cost = $cost;
        $this->freq = $freq;
        $this->lastAccess = $lastAccess;
        $this->admitFeatures = $admitFeatures;
    }
}
