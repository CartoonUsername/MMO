// Legt beim Start jeder Szene automatisch den Spielcontroller an – es muss nichts von Hand in die Szene gezogen werden.
using UnityEngine;

namespace Mmo
{
    public static class Bootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Init()
        {
            if (Object.FindFirstObjectByType<GameController>() == null) new GameObject("MMO").AddComponent<GameController>();
        }
    }
}
