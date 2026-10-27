<?php
// Bouchons minimaux de Zend_Cache (ZF1) pour tester le backend hors Magento.
class Zend_Cache { const CLEANING_MODE_ALL = 'all'; const CLEANING_MODE_OLD = 'old';
  const CLEANING_MODE_MATCHING_TAG = 'matchingTag'; const CLEANING_MODE_NOT_MATCHING_TAG = 'notMatchingTag';
  const CLEANING_MODE_MATCHING_ANY_TAG = 'matchingAnyTag'; }
interface Zend_Cache_Backend_Interface { }
interface Zend_Cache_Backend_ExtendedInterface extends Zend_Cache_Backend_Interface { }
class Zend_Cache_Backend { protected $_options = array(); public function setDirectives($d) {} }
class Stub_Array_Backend extends Zend_Cache_Backend implements Zend_Cache_Backend_ExtendedInterface {
  public $d = array(); public $t = array();
  public function __construct($o = array()) {}
  public function load($id, $x = false) { return isset($this->d[$id]) ? $this->d[$id] : false; }
  public function test($id) { return isset($this->d[$id]); }
  public function save($data, $id, $tags = array(), $l = false) { $this->d[$id] = $data; $this->t[$id] = $tags; return true; }
  public function remove($id) { unset($this->d[$id], $this->t[$id]); return true; }
  public function clean($mode = 'all', $tags = array()) {
    $ids = $mode === 'all' ? $this->getIds() : ($mode === 'matchingTag' ? $this->getIdsMatchingTags($tags) : $this->getIdsMatchingAnyTags($tags));
    foreach ($ids as $id) $this->remove($id); return true; }
  public function getIds() { return array_keys($this->d); }
  public function getTags() { return array(); }
  public function getIdsMatchingTags($tags = array()) { $o = array(); foreach ($this->t as $id => $t) if (!array_diff($tags, $t)) $o[] = $id; return $o; }
  public function getIdsNotMatchingTags($tags = array()) { return array_values(array_diff($this->getIds(), $this->getIdsMatchingAnyTags($tags))); }
  public function getIdsMatchingAnyTags($tags = array()) { $o = array(); foreach ($this->t as $id => $t) if (array_intersect($tags, $t)) $o[] = $id; return $o; }
  public function getFillingPercentage() { return 0; } public function getMetadatas($id) { return false; }
  public function touch($id, $e) { return true; } public function getCapabilities() { return array(); }
}
