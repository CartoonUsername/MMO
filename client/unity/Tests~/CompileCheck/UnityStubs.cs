// Minimale Nachbildung der benutzten UnityEngine-Schnittstellen - NUR zur Übersetzungsprüfung außerhalb von Unity (Tippfehler, Typfehler).
// Verhalten ist leer; die Signaturen folgen der Unity-6-Dokumentation. Kein Ersatz für einen echten Test in Unity.
using System;

namespace UnityEngine
{
    public class Object { public string name; public static void Destroy(Object o) { } public static T FindFirstObjectByType<T>() where T : Object { return null; } public static implicit operator bool(Object o) { return o != null; } }
    public class Component : Object { public Transform transform; public T GetComponent<T>() where T : class { return null; } }
    public class Behaviour : Component { }
    public class MonoBehaviour : Behaviour { }
    public class Collider : Component { }
    public class Material { public Color color; }
    public class Renderer : Component { public Material material; }
    public class Camera : Component { public static Camera main; }
    public class Transform : Component { public Vector3 position; public Vector3 localScale; public void LookAt(Vector3 p) { } }
    public enum PrimitiveType { Sphere, Capsule, Cylinder, Cube, Plane, Quad }
    public class GameObject : Object
    {
        public Transform transform = new Transform(); public GameObject() { } public GameObject(string name, params Type[] components) { }
        public static GameObject CreatePrimitive(PrimitiveType t) { return new GameObject(); }
        public T AddComponent<T>() where T : Component, new() { return new T(); }
        public T GetComponent<T>() where T : class { return null; }
    }
    public struct Vector2 { public float x, y; }
    public struct Vector2Int : IEquatable<Vector2Int>
    {
        public int x, y; public Vector2Int(int x, int y) { this.x = x; this.y = y; }
        public bool Equals(Vector2Int o) { return x == o.x && y == o.y; }
        public override bool Equals(object o) { return o is Vector2Int v && Equals(v); }
        public override int GetHashCode() { return x * 31 + y; }
        public static bool operator ==(Vector2Int a, Vector2Int b) { return a.Equals(b); }
        public static bool operator !=(Vector2Int a, Vector2Int b) { return !a.Equals(b); }
    }
    public struct Vector3
    {
        public float x, y, z; public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 one => new Vector3(1, 1, 1); public static Vector3 up => new Vector3(0, 1, 0);
        public static Vector3 operator +(Vector3 a, Vector3 b) { return new Vector3(a.x + b.x, a.y + b.y, a.z + b.z); }
        public static Vector3 operator *(Vector3 a, float f) { return new Vector3(a.x * f, a.y * f, a.z * f); }
        public static Vector3 Lerp(Vector3 a, Vector3 b, float t) { return a; }
        public static float Distance(Vector3 a, Vector3 b) { return 0f; }
    }
    public struct Color { public Color(float r, float g, float b) { } }
    public struct Rect { public Rect(float x, float y, float w, float h) { } }
    public static class Mathf { public static float Max(float a, float b) { return a > b ? a : b; } }
    public static class Time { public static float time; }
    public static class Screen { public static int width, height; }
    public enum KeyCode { A, D, S, W, E, F, Q, R, C, V, Tab, Space, Alpha1, Alpha2, Alpha3, Alpha4, Alpha5, Alpha6, Alpha7, Alpha8, Alpha9 }
    public static class Input { public static bool GetKey(KeyCode k) { return false; } public static bool GetKeyDown(KeyCode k) { return false; } public static bool GetMouseButtonDown(int b) { return false; } }
    public enum RuntimeInitializeLoadType { AfterSceneLoad }
    [AttributeUsage(AttributeTargets.Method)] public class RuntimeInitializeOnLoadMethodAttribute : Attribute { public RuntimeInitializeOnLoadMethodAttribute(RuntimeInitializeLoadType t) { } }
    public class GUIStyle { }
    public class GUISkin { public GUIStyle box, button; }
    public class GUILayoutOption { }
    public static class GUI
    {
        public static GUISkin skin = new GUISkin();
        public static void Box(Rect r, string text) { }
        public static bool Button(Rect r, string text) { return false; }
    }
    public static class GUILayout
    {
        public static void BeginArea(Rect r) { } public static void BeginArea(Rect r, GUIStyle s) { } public static void EndArea() { }
        public static void BeginHorizontal() { } public static void EndHorizontal() { }
        public static Vector2 BeginScrollView(Vector2 p, params GUILayoutOption[] o) { return p; } public static void EndScrollView() { }
        public static void Label(string t) { } public static void Label(string t, params GUILayoutOption[] o) { }
        public static string TextField(string t) { return t; } public static string PasswordField(string t, char c) { return t; }
        public static bool Button(string t) { return false; } public static bool Button(string t, params GUILayoutOption[] o) { return false; }
        public static bool Toggle(bool v, string t, GUIStyle s) { return v; }
        public static GUILayoutOption Width(float w) { return null; } public static GUILayoutOption Height(float h) { return null; } public static GUILayoutOption ExpandWidth(bool b) { return null; }
    }
}
