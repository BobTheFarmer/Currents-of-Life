Shader "Build4Good/ScrollingWater"
{
    Properties
    {
        _MainTex ("Water Texture", 2D) = "white" {}
        _Offset  ("UV Scroll Offset (camera + base flow)", Vector) = (0, 0, 0, 0)
    }
    SubShader
    {
        Tags
        {
            "RenderType"    = "Opaque"
            "RenderPipeline" = "UniversalPipeline"
            "Queue"         = "Background-1"
        }

        Pass
        {
            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float4 _Offset;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 uv         : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionHCS : SV_POSITION;
                float2 uv          : TEXCOORD0;
            };

            Varyings vert(Attributes IN)
            {
                Varyings OUT;
                OUT.positionHCS = TransformObjectToHClip(IN.positionOS.xyz);
                // Camera position + base current flow baked in by OceanBackground.cs
                OUT.uv = IN.uv * _MainTex_ST.xy + _MainTex_ST.zw + _Offset.xy;
                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target
            {
                float2 uv = IN.uv;
                float  t  = _Time.y;

                // ── Layer 1: surface current (slow, fine-scale shear) ──────────
                // Streamlines at different Y positions move at slightly different
                // eastward speeds — this is what makes them "grind" against each other.
                float s1x = sin(uv.y * 6.8  + t * 0.032) * 0.048
                          + sin(uv.y * 2.3  - t * 0.018) * 0.072
                          + sin(uv.y * 14.1 + t * 0.041) * 0.021;
                float s1y = cos(uv.x * 4.7  + t * 0.022) * 0.028
                          + sin(uv.x * 10.2 - t * 0.028) * 0.014;

                // ── Layer 2: mesoscale eddies (very slow, large-scale rotation) ─
                float s2x = sin(uv.y * 1.2 + uv.x * 0.6 + t * 0.009) * 0.055
                          + cos(uv.y * 0.7 - uv.x * 1.1 - t * 0.006) * 0.038;
                float s2y = cos(uv.x * 0.9 + uv.y * 1.4 + t * 0.007) * 0.042
                          + sin(uv.x * 1.8 - uv.y * 0.5 - t * 0.005) * 0.026;

                // Combined distortion for primary sample
                float2 uvA = uv + float2(s1x + s2x, s1y + s2y);

                return SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uvA);
            }
            ENDHLSL
        }
    }
}
