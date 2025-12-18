# app/lru.py

class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class DoublyLinkedList:
    def __init__(self):
        self.head = Node(None, None)
        self.tail = Node(None, None)

        self.head.next = self.tail
        self.tail.prev = self.head

    def add_to_front(self, node):
        node.next = self.head.next
        node.prev = self.head

        self.head.next.prev = node
        self.head.next = node

    def remove_node(self, node):
        prev_node = node.prev
        next_node = node.next

        prev_node.next = next_node
        next_node.prev = prev_node

    def remove_from_end(self):
        if self.tail.prev == self.head:
            return None
        lru = self.tail.prev
        self.remove_node(lru)
        return lru


class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}  # key → Node
        self.dll = DoublyLinkedList()

    def get(self, key):
        if key not in self.cache:
            return None

        node = self.cache[key]
        self.dll.remove_node(node)
        self.dll.add_to_front(node)
        return node.value

    def put(self, key, value):
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self.dll.remove_node(node)
            self.dll.add_to_front(node)
        else:
            if len(self.cache) >= self.capacity:
                lru = self.dll.remove_from_end()
                if lru:
                    del self.cache[lru.key]

            new_node = Node(key, value)
            self.dll.add_to_front(new_node)
            self.cache[key] = new_node

    def delete(self, key):
        if key in self.cache:
            node = self.cache[key]
            self.dll.remove_node(node)
            del self.cache[key]
            return True
        return False
